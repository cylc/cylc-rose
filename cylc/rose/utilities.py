# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Cylc support for reading and interpreting ``rose-suite.conf`` files."""

import itertools
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.flags import cylc7_back_compat
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import get_host
from metomi.isodatetime.datetimeoper import DateTimeOperator
from metomi.rose import __version__ as ROSE_VERSION
from metomi.rose.config import (
    ConfigDumper,
    ConfigLoader,
    ConfigNode,
    ConfigNodeDiff,
)
from metomi.rose.config_processor import ConfigProcessError
from metomi.rose.config_tree import ConfigTree
from metomi.rose.env import UnboundEnvironmentVariableError, env_var_process

from cylc.rose.jinja2_parser import Parser, patch_jinja2_leading_zeros

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Values


ROSE_SUITE_OPT_CONF_KEYS = 'ROSE_SUITE_OPT_CONF_KEYS'
SECTIONS = {'jinja2:suite.rc', 'empy:suite.rc', 'template variables'}
SET_BY_CYLC = 'set by Cylc'
ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING = (
    ' ROSE_ORIG_HOST set by cylc install.'
)
MESSAGE = 'message'
ALL_MODES = 'all modes'


class NotARoseSuiteException(Exception):
    def __str__(self):
        msg = (
            'Cylc-Rose CLI arguments only used '
            'if a rose-suite.conf file is present:'
            '\n * "--opt-conf-key" or "-O"'
            '\n * "--define" or "-D"'
            '\n * "--rose-template-variable" or "-S"'
        )
        return msg


class MultipleTemplatingEnginesError(CylcError):
    ...


class InvalidDefineError(CylcError):
    ...


def process_config(
    config_tree: 'ConfigTree',
    environ=os.environ,
) -> Dict[str, Any]:
    """Process template and environment variables.

    Note:
        This uses only the provided config node and environment variables,
        there is no system interaction.

    Args:
        config_tree:
            Configuration node representing the Rose suite configuration.
        environ:
            Dictionary of environment variables (for testing).

    """
    plugin_result: Dict[str, Any] = {
        # default return value
        'env': {},
        'template_variables': {},
        'templating_detected': None
    }
    config_node = config_tree.node

    # Don't allow multiple templating sections.
    templating = identify_templating_section(config_node)

    if templating != 'template variables':
        plugin_result['templating_detected'] = templating.replace(
            ':suite.rc',
            '',
        )
    else:
        plugin_result['templating_detected'] = templating

    # Create env section if it doesn't already exist.
    if 'env' not in config_node.value:
        config_node.set(['env'])
    if templating not in config_node.value:
        config_node.set([templating])

    # Get Rose Orig host:
    rose_orig_host = get_host()

    # For each section process variables and add standard variables.
    for section in ['env', templating]:

        # This loop handles standard variables.
        # CYLC_VERSION - If it's in the config, remove it.
        # ROSE_VERSION - If it's in the config, replace it.
        # ROSE_ORIG_HOST - If it's the config, replace it, unless it has a
        # comment marking it as having been saved by ``cylc install``.
        # In all cases warn users if the value in their config is not used.
        for var_name, replace_with in [
            ('ROSE_ORIG_HOST', rose_orig_host),
            ('ROSE_VERSION', ROSE_VERSION),
            ('CYLC_VERSION', SET_BY_CYLC)
        ]:
            # Warn if we're we're going to override a variable:
            if override_this_variable(config_node, section, var_name):
                user_var = config_node[section].value[var_name].value
                LOG.warning(
                    f'[{section}]{var_name}={user_var} from rose-suite.conf '
                    f'will be ignored: {var_name} will be: {replace_with}'
                )

            # Handle replacement of stored variable if appropriate:
            if replace_with == SET_BY_CYLC:
                config_node[section].unset([var_name])
            elif not rose_orig_host_set_by_cylc_install(
                config_node, section, var_name
            ):
                config_node[section].set([var_name], replace_with)

        # Use env_var_process to process variables which may need expanding.
        for key, node in config_node.value[section].value.items():
            try:
                config_node.value[
                    section
                ].value[key].value = env_var_process(
                    node.value,
                    environ=environ
                )
                if section == 'env':
                    environ[key] = node.value
            except UnboundEnvironmentVariableError as exc:
                raise ConfigProcessError(['env', key], node.value, exc)

    # For each of the template language sections extract items to a simple
    # dict to be returned.
    plugin_result['env'] = {
        item[0][1]: item[1].value for item in
        config_node.value['env'].walk()
        if item[1].state == ConfigNode.STATE_NORMAL
    }
    plugin_result['template_variables'] = {
        item[0][1]: item[1].value for item in
        config_node.value[templating].walk()
        if item[1].state == ConfigNode.STATE_NORMAL
    }

    # Add the entire plugin_result to ROSE_SUITE_VARIABLES to allow for
    # programatic access.
    with patch_jinja2_leading_zeros():
        # BACK COMPAT: patch_jinja2_leading_zeros
        # back support zero-padded integers for a limited time to help
        # users migrate before upgrading cylc-flow to Jinja2>=3.1
        parser = Parser()
        for key, value in plugin_result['template_variables'].items():
            # The special variables are already Python variables.
            if key not in ['ROSE_ORIG_HOST', 'ROSE_VERSION', 'ROSE_SITE']:
                try:
                    plugin_result['template_variables'][key] = (
                        parser.literal_eval(value)
                    )
                except Exception:
                    raise ConfigProcessError(
                        [templating, key],
                        value,
                        f'Invalid template variable: {value}'
                        '\nMust be a valid Python or Jinja2 literal'
                        ' (note strings "must be quoted").'
                    ) from None

    # Add ROSE_SUITE_VARIABLES to plugin_result of templating engines in use.
    plugin_result['template_variables'][
        'ROSE_SUITE_VARIABLES'] = plugin_result['template_variables']

    return plugin_result


def identify_templating_section(config_node):
    """Get the name of the templating section.

    Raises MultipleTemplatingEnginesError if multiple
    templating sections exist.
    """
    defined_sections = SECTIONS.intersection(set(config_node.value.keys()))
    if len(defined_sections) > 1:
        raise MultipleTemplatingEnginesError(
            "You should not define more than one templating section. "
            f"You defined:\n\t{'; '.join(defined_sections)}"
        )
    elif defined_sections:
        return id_templating_section(defined_sections.pop())
    else:
        return id_templating_section('')


def id_templating_section(
    section: Optional[str] = None,
    with_brackets: bool = False
) -> str:
    """Return a full template section string."""
    templating = None
    if section and 'jinja2' in section:
        templating = 'jinja2:suite.rc'
    elif section and 'empy' in section:
        templating = 'empy:suite.rc'

    if not templating:
        templating = 'template variables'

    templating = f'[{templating}]' if with_brackets else templating
    return templating


def rose_config_exists(dir_: Path) -> bool:
    """Does dir_ a rose config?

    Args:
        dir_: location to test.

    Returns:
        True if a ``rose-suite.conf`` exists, or option config items have
        been set.
    """
    return (dir_ / 'rose-suite.conf').is_file()


def rose_config_tree_loader(
    srcdir: Path,
    opts: 'Optional[Values]',
) -> ConfigTree:
    """Get a rose config tree from srcdir.

    Args:
        srcdir(string or Pathlib.path object):
            Search for a ``rose-suite.conf`` file in this location.
        opts:
            Options namespace: To be used to allow CLI
            specification of optional configuarations.
    Returns:
        A Rose ConfigTree object.
    """
    opt_conf_keys = []

    # get optional config key set as environment variable:
    opt_conf_keys_env = os.getenv(ROSE_SUITE_OPT_CONF_KEYS)
    if opt_conf_keys_env:
        opt_conf_keys += shlex.split(opt_conf_keys_env)

    # ... or as command line options
    if opts and 'opt_conf_keys' in dir(opts) and opts.opt_conf_keys:
        if isinstance(opts.opt_conf_keys, str):
            opt_conf_keys += opts.opt_conf_keys.split()
        else:
            opt_conf_keys += opts.opt_conf_keys

    # Optional definitions
    redefinitions = []
    if opts and 'defines' in dir(opts) and opts.defines:
        redefinitions = opts.defines

    # Load the config tree
    from metomi.rose.config_tree import ConfigTreeLoader
    config_tree = ConfigTreeLoader().load(
        str(srcdir),
        'rose-suite.conf',
        opt_keys=opt_conf_keys,
        defines=redefinitions,
    )

    # Reload the Config using the suite_ variables.
    # (we can't do this first time around because we have no idea what the
    # templating section is.)
    if opts and getattr(opts, 'rose_template_vars', None):
        template_section = identify_templating_section(config_tree.node)
        for template_var in opts.rose_template_vars or []:
            redefinitions.append(f'[{template_section}]{template_var}')
        # Reload the config
        config_tree = ConfigTreeLoader().load(
            str(srcdir),
            'rose-suite.conf',
            opt_keys=opt_conf_keys,
            defines=redefinitions,
        )

    return config_tree


def merge_rose_cylc_suite_install_conf(old, new):
    """Merge old and new ``rose-suite-cylc-install.conf`` configs nodes.

    Opts are merged separately to allow special behaviour.
    The rest is merged using ConfigNodeDiff.

    If the template language has changed, use the new templating language.

    Args:
        old, new (ConfigNode):
            Old and new nodes.

    Returns:
        ConfigNode representing config to be written to the rundir.

    Example:
        >>> from metomi.rose.config import ConfigNode;
        >>> old = ConfigNode({'opts': ConfigNode('a b c')})
        >>> new = ConfigNode({'opts': ConfigNode('c d e')})
        >>> merge_rose_cylc_suite_install_conf(old, new)['opts']
        {'value': 'a b c d e', 'state': '', 'comments': []}
    """
    # remove jinja2/empy:suite.rc from old if template variables in new
    for before, after in itertools.permutations(SECTIONS, 2):
        if new.value.get(after, '') and old.value.get(before, ''):
            # Choosing not to warn if user downgrades here because
            # other checks warn of old sections.
            old.value[after] = old.value[before]
            old.value.pop(before)

    # Special treatement of opts key:
    if 'opts' in old and 'opts' in new:
        new_opts_str = f'{old["opts"].value} {new["opts"].value}'
        new['opts'].value = simplify_opts_strings(new_opts_str)
    elif 'opts' in old:
        new.set(['opts'], old['opts'].value)

    # Straightforward merge of the rest of the configs.
    diff = ConfigNodeDiff()
    diff.set_from_configs(old, new)
    diff.delete_removed()
    old.add(diff)

    return old


def invalid_defines_check(defines: List) -> None:
    """Check for defines which do not contain an = and therefore cannot be
    valid

    Examples:

        # A single invalid define:
        >>> import pytest
        >>> with pytest.raises(InvalidDefineError, match=r'\\* foo'):
        ...    invalid_defines_check(['foo'])

        # Two invalid defines and one valid one:
        >>> with pytest.raises(
        ...     InvalidDefineError, match=r'\\* foo.*\\n.* \\* bar'
        ... ):
        ...     invalid_defines_check(['foo', 'bar52', 'baz=442'])

        # No invalid defines
        >>> invalid_defines_check(['foo=12'])
    """
    invalid_defines = []
    for define in defines:
        if parse_cli_defines(define) is False:
            invalid_defines.append(define)
    if invalid_defines:
        msg = 'Invalid Suite Defines (should contain an =)'
        for define in invalid_defines:
            msg += f'\n * {define}'
        raise InvalidDefineError(msg)


def parse_cli_defines(define: str) -> Union[
    bool, str, Tuple[
        List[Union[str, Any]],
        Union[str, Any],
        Union[str, Any],
    ]
]:
    """Parse a define string.

    Args:
        define:
            A string in one of two forms:
            - `key = "value"`
            - `[section]key = "value"`

            With optional `!` and `!!` prepended, indicating an ignored state,
            which should lead to a warning being logged.

    Returns:
        False: If state is ignored or trigger-ignored, otherwise...
        (keys, value, state)

    Examples:
        # Top level key
        >>> parse_cli_defines('root-dir = "foo"')
        (['root-dir'], '"foo"', '')

        # Marked as ignored
        >>> parse_cli_defines('!root-dir = "foo"')
        False

        # Inside a section
        >>> parse_cli_defines('[section]orange = "segment"')
        (['section', 'orange'], '"segment"', '')
    """
    match = re.match(
        (
            r'^\[(?P<section>.*)\](?P<state>!{0,2})'
            r'(?P<key>.*)\s*=\s*(?P<value>.*)'
        ),
        define
    )
    if match:
        groupdict = match.groupdict()
        keys = [groupdict['section'].strip(), groupdict['key'].strip()]
    else:
        # Doesn't have a section:
        match = re.match(
            r'^(?P<state>!{0,2})(?P<key>.*)\s*=\s*(?P<value>.*)', define)
        if match and not match['state']:
            groupdict = match.groupdict()
            keys = [groupdict['key'].strip()]
        else:
            # This seems like it ought to be an error,
            # But behaviour is consistent with Rose 2019
            # See: https://github.com/cylc/cylc-rose/issues/217
            return False

    return (keys, match['value'], match['state'])


def get_cli_opts_node(srcdir: Path, opts: 'Values'):
    """Create a ConfigNode representing options set on the command line.

    Args:
        opts (CylcOptionParser object):
            Object with values from the command line.

    Returns:
        Rose ConfigNode.

    Example:
        >>> from types import SimpleNamespace
        >>> from pathlib import Path
        >>> opts = SimpleNamespace(
        ...     opt_conf_keys='A B',
        ...     defines=["[env]FOO=BAR"],
        ...     rose_template_vars=["QUX=BAZ"]
        ... )
        >>> node = get_cli_opts_node(Path('no/such/dir'), opts)
        >>> node['opts']
        {'value': 'A B', 'state': '!', 'comments': []}
        >>> node['env']['FOO']
        {'value': 'BAR', 'state': '', 'comments': []}
        >>> node['template variables']['QUX']
        {'value': 'BAZ', 'state': '', 'comments': []}
    """
    # Unpack info we want from opts:
    opt_conf_keys: list = []
    defines: list = []
    rose_template_vars: list = []
    if opts and 'opt_conf_keys' in dir(opts):
        opt_conf_keys = opts.opt_conf_keys or []
    if opts and 'defines' in dir(opts):
        defines = opts.defines or []
    if opts and 'rose_template_vars' in dir(opts):
        rose_template_vars = opts.rose_template_vars or []

    rose_orig_host = get_host()
    defines.append(f'[env]ROSE_ORIG_HOST={rose_orig_host}')
    rose_template_vars.append(f'ROSE_ORIG_HOST={rose_orig_host}')

    # Construct new config node representing CLI config items:
    newconfig = ConfigNode()
    newconfig.set(['opts'], ConfigNode())

    # For each __define__ determine whether it is an env or template define.
    for define in defines:
        parsed_define = parse_cli_defines(define)
        if parsed_define:
            newconfig.set(*parsed_define)

    # For each __suite define__ add define.
    templating: str
    if not rose_config_exists(srcdir):
        templating = 'template variables'
    else:
        templating = identify_templating_section(
            rose_config_tree_loader(srcdir, opts).node
        )

    for define in rose_template_vars:
        _match = re.match(
            r'(?P<state>!{0,2})(?P<key>.*)\s*=\s*(?P<value>.*)', define
        )
        if not _match:
            raise ValueError(f'Invalid define: {define}')
        _match_groups = _match.groupdict()
        # Guess templating type?
        newconfig.set(
            keys=[templating, _match_groups['key']],
            value=_match_groups['value'],
            state=_match_groups['state']
        )

    # Specialised treatement of optional configs.
    newconfig['opts'].value = ''
    newconfig['opts'].value = merge_opts(newconfig, opt_conf_keys)
    newconfig['opts'].state = '!'

    return newconfig


def add_cylc_install_to_rose_conf_node_opts(rose_conf, cli_conf):
    """Combine file based config opts with CLI config.

    Args:
        rose_conf (ConfigNode):
            A config node representing settings loaded from files.
        cli_conf (ConfigNode):
            A config node representing settings loaded from the CLI

    Returns:
        A combined ConfigNode.
    """

    if 'opts' in cli_conf:
        cli_opts = cli_conf['opts'].value
    else:
        cli_opts = ''
    if 'opts' not in rose_conf:
        rose_conf.set(['opts'], '')
    rose_conf['opts'].comments = [(
        f' Config Options \'{cli_opts} (cylc-install)\' from CLI appended to '
        'options already in `rose-suite.conf`.'
    )]
    opts = []
    if rose_conf['opts'].state not in ['!', '!!']:
        opts += rose_conf["opts"].value.split()
    opts += cli_opts.split() + ['(cylc-install)']
    rose_conf['opts'].value = ' '.join(opts)
    rose_conf['opts'].state = ''
    return rose_conf


def merge_opts(config, opt_conf_keys):
    """Merge all options in specified order.

    Adds the keys for optional configs in order of increasing priority.
    Later items in the resultant string will over-ride earlier items.
    - Opts set using ``cylc install --defines "[]opts=A B C"``.
    - Opts set by setting ``ROSE_SUITE_OPT_CONF_KEYS="C D E"`` in environment.
    - Opts sey using ``cylc install --opt-conf-keys "E F G".

    In the example above the string returned would be "A B C D E F G".

    Args:
        config (ConfigNode):
            Config where opts has been added using ``--defines "[]opts=X"``.
        opt_conf_key (list | string):
            Options set using ``--opt-conf-keys "Y"`

    Returns:
        String containing opt conf keys sorted and with only the last of any
        duplicate.

    Examples:
        >>> from types import SimpleNamespace; conf = SimpleNamespace()
        >>> conf.value = 'aleph'; conf = {'opts': conf}

        Merge options from opt_conf_keys and defines.
        >>> merge_opts(conf, 'gimmel')
        'aleph gimmel'

        Merge options from defines and environment.
        >>> from pytest import MonkeyPatch
        >>> with MonkeyPatch.context() as mp:
        ...     mp.setenv('ROSE_SUITE_OPT_CONF_KEYS', 'bet')
        ...     merge_opts(conf, '')
        'aleph bet'

        Merge all three options.
        Merge all three options.
        >>> with MonkeyPatch.context() as mp:
        ...     mp.setenv('ROSE_SUITE_OPT_CONF_KEYS', 'bet')
        ...     merge_opts(conf, 'gimmel')
        'aleph bet gimmel'
    """
    all_opt_conf_keys = []
    all_opt_conf_keys.append(config['opts'].value)
    if ROSE_SUITE_OPT_CONF_KEYS in os.environ:
        all_opt_conf_keys.append(os.environ[ROSE_SUITE_OPT_CONF_KEYS])
    if opt_conf_keys and isinstance(opt_conf_keys, str):
        all_opt_conf_keys.append(opt_conf_keys)
    if opt_conf_keys and isinstance(opt_conf_keys, list):
        all_opt_conf_keys += opt_conf_keys
    return simplify_opts_strings(' '.join(all_opt_conf_keys))


def simplify_opts_strings(opts):
    """Merge Opts strings:

    Rules:
        - Items in new come after items in old.
        - Items in new are removed from old.
        - Otherwise order is preserved.

    Args:
        opts (str):
            a string containing a space delimeted list of options.
    Returns (str):
        A string which acts as a space delimeted list.

    Examples:
        >>> simplify_opts_strings('a b c')
        'a b c'
        >>> simplify_opts_strings('a b b')
        'a b'
        >>> simplify_opts_strings('a b a')
        'b a'
        >>> simplify_opts_strings('a b c d b')
        'a c d b'
        >>> simplify_opts_strings('a b c b d')
        'a c b d'
        >>> simplify_opts_strings('a b a b a a b b b c a b hello')
        'c a b hello'
    """

    seen_once = []
    for _index, item in enumerate(reversed(opts.split())):
        if item not in seen_once:
            seen_once.append(item)

    return ' '.join(reversed(seen_once))


def dump_rose_log(rundir: Path, node: ConfigNode):
    """Dump a config node to a timestamped file in the ``log`` sub-directory.

    Args:
        rundir (pathlib.Path):
            Installed location of a flow.
        node (Rose Config node):
            Node to be dumped to file.

    Returns:
        String filepath of the dump file relative to the install directory.
    """
    dumper = ConfigDumper()
    timestamp = DateTimeOperator().process_time_point_str(
        print_format='%Y%m%dT%H%M%S%z'
    )
    rel_path = f'log/config/{timestamp}-rose-suite.conf'
    fpath = rundir / rel_path
    fpath.parent.mkdir(exist_ok=True, parents=True)
    dumper.dump(node, str(fpath))
    return rel_path


def override_this_variable(node, section, variable):
    """Variable exists in this section of the config and should be replaced
    because it is a standard variable.

    Examples:
        Setup:
        >>> from metomi.rose.config import ConfigNode
        >>> from cylc.rose.utilities import (
        ... ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING as rohios
        ... )
        >>> node = ConfigNode()
        >>> node = node.set(['env'])

        1. Variable not in node[section]:
        >>> override_this_variable(node, 'env', 'foo')
        False

        2. Variable is not ROSE_ORIG_HOST:
        >>> node = node.set(['env', 'ROSE_VERSION'], '123.456')
        >>> override_this_variable(node, 'env', 'ROSE_VERSION')
        True

        3. Variable is ROSE_ORIG_HOST and override string unset:
        >>> node = node.set(['env', 'ROSE_ORIG_HOST'], '123.456.789.10')
        >>> override_this_variable(node, 'env', 'ROSE_ORIG_HOST')
        True

        4. Variable is ROSE_ORIG_HOST and override string set:
        >>> node['env']['ROSE_ORIG_HOST'].comments = [rohios]
        >>> override_this_variable(node, 'env', 'ROSE_ORIG_HOST')
        False
    """
    if variable not in node[section]:
        return False
    elif (
        variable != 'ROSE_ORIG_HOST'
        or (
            ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING not in
            node[section][variable].comments
        )
    ):
        return True
    return False


def rose_orig_host_set_by_cylc_install(node, section, var):
    """ROSE_ORIG_HOST exists in node and is commented by Cylc Install to avoid
    it being overridden by Cylc Rose.

    Examples:
        Setup:
        >>> from metomi.rose.config import ConfigNode
        >>> from cylc.rose.utilities import (
        ... ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING as rohios
        ... )
        >>> node = ConfigNode()

        ROSE_ORIG_HOST set by user, without the comment which Cylc install
        would add:
        >>> node = node.set(['env', 'ROSE_ORIG_HOST'], 'IMPLAUSIBLE_HOST_NAME')
        >>> rose_orig_host_set_by_cylc_install(node, 'env', 'ROSE_ORIG_HOST')
        False

        ROSE_ORIG_HOST set by Cylc install, with a comment saying so:
        >>> node['env']['ROSE_ORIG_HOST'].comments = rohios
        >>> rose_orig_host_set_by_cylc_install(node, 'env', 'ROSE_ORIG_HOST')
        True
    """
    if (
        var in node[section]
        and ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING in
        node[section][var].comments
    ):
        return True
    return False


def deprecation_warnings(config_tree):
    """Check for deprecated items in config.
    Logs a warning for deprecated items:
        - "root-dir"
        - "jinja2:suite.rc"
        - "empy:suite.rc"
        - root-dir

    If ALL_MODES is True this deprecation will ignore whether there is a
    flow.cylc or suite.rc in the workflow directory.
    """

    deprecations = {
        'empy:suite.rc': {
            MESSAGE: (
                "'rose-suite.conf[empy:suite.rc]' is deprecated."
                " Use [template variables] instead."),
            ALL_MODES: False,
        },
        'jinja2:suite.rc': {
            MESSAGE: (
                "'rose-suite.conf[jinja2:suite.rc]' is deprecated."
                " Use [template variables] instead."),
            ALL_MODES: False,
        },
        'empy:flow.cylc': {
            MESSAGE: (
                "'rose-suite.conf[empy:flow.cylc]' is not used by Cylc."
                " Use [template variables] instead."),
            ALL_MODES: False,
        },
        'jinja2:flow.cylc': {
            MESSAGE: (
                "'rose-suite.conf[jinja2:flow.cylc]' is not used by Cylc."
                " Use [template variables] instead."),
            ALL_MODES: False,
        },
        'root-dir': {
            MESSAGE: (
                'You have set "rose-suite.conf[root-dir]", '
                'which is not supported at '
                'Cylc 8. Use `[install] symlink dirs` in global.cylc '
                'instead.'),
            ALL_MODES: True,
        },
    }
    for string in list(config_tree.node):
        for name, info in deprecations.items():
            if (
                (info[ALL_MODES] or not cylc7_back_compat)
                and name in string.lower()
            ):
                LOG.warning(info[MESSAGE])


def load_rose_config(
    srcdir: Path,
    opts: 'Optional[Values]' = None,
) -> 'ConfigTree':
    """Load rose configuration from srcdir.

    Load template variables from Rose suite configuration.

    Loads the Rose suite configuration tree from the filesystem
    using the shell environment.

    Args:
        srcdir:
            Path to the Rose suite configuration
            (the directory containing the ``rose-suite.conf`` file).
        opts:
            Options object containing specification of optional
            configuarations set by the CLI.

            Note: this is None for "rose stem" usage.

    Returns:
        The Rose configuration tree for "srcdir".

    """
    # Return a blank config dict if srcdir does not exist
    if not rose_config_exists(srcdir):
        if (
            opts
            and (
                getattr(opts, "opt_conf_keys", None)
                or getattr(opts, "defines", None)
                or getattr(opts, "rose_template_vars", None)
            )
        ):
            raise NotARoseSuiteException()
        return ConfigTree()

    # Check for definitely invalid defines
    if opts and hasattr(opts, 'defines'):
        invalid_defines_check(opts.defines)

    # Load the raw config tree
    config_tree = rose_config_tree_loader(srcdir, opts)
    deprecation_warnings(config_tree)

    return config_tree


def export_environment(environment: Dict[str, str]) -> None:
    # Export environment vars
    for key, val in environment.items():
        os.environ[key] = val

    # If env vars have been set we want to force reload
    # the global config so that the value of this vars
    # can be used by Jinja2 in the global config.
    # https://github.com/cylc/cylc-rose/issues/237
    if environment:
        glbl_cfg().load()


def record_cylc_install_options(
    srcdir: Path,
    rundir: Path,
    opts: 'Values',
) -> Tuple[ConfigNode, ConfigNode]:
    """Create/modify files recording Cylc install config options.

    Creates a new config based on CLI options and writes it to the workflow
    install location as ``rose-suite-cylc-install.conf``.

    If ``rose-suite-cylc-install.conf`` already exists over-writes changed
    items, except for ``!opts=`` which is merged and simplified.

    If ``!opts=`` have been changed these are appended to those that have
    been written in the installed ``rose-suite.conf``.

    Args:
        srcdir:
            Used to check whether the source directory contains a rose config.
        rundir:
            Path to dump the rose-suite-cylc-conf
        opts:
            Cylc option parser object - we want to extract the following
            values:
            - opt_conf_keys (list of str):
                Equivalent of ``rose suite-run --option KEY``
            - defines (list of str):
                Equivalent of ``rose suite-run --define KEY=VAL``
            - rose_template_vars (list of str):
                Equivalent of ``rose suite-run --define-suite KEY=VAL``

    Returns:
        Tuple - (cli_config, rose_suite_conf)

        cli_config:
            The Cylc install config aka "rose-suite-cylc-install.conf".
        rose_suite_conf:
            The "opts" section of the config node dumped to
            installed ``rose-suite.conf``.

    """
    # Create a config based on command line options:
    cli_config = get_cli_opts_node(srcdir, opts)

    # raise error if CLI config has multiple templating sections
    identify_templating_section(cli_config)

    # Construct path objects representing our target files.
    (Path(rundir) / 'opt').mkdir(exist_ok=True)
    conf_filepath = Path(rundir) / 'opt/rose-suite-cylc-install.conf'
    rose_conf_filepath = Path(rundir) / 'rose-suite.conf'
    dumper = ConfigDumper()
    loader = ConfigLoader()

    # If file exists we need to merge with our new config, over-writing with
    # new items where there are duplicates.
    if conf_filepath.is_file():
        if opts.clear_rose_install_opts:
            conf_filepath.unlink()
        else:
            oldconfig = loader.load(str(conf_filepath))
            # Check old config for clashing template variables sections.
            identify_templating_section(oldconfig)
            cli_config = merge_rose_cylc_suite_install_conf(
                oldconfig, cli_config
            )

    # Get Values for standard ROSE variable ROSE_ORIG_HOST.
    rose_orig_host = get_host()
    for section in [
        'env', 'jinja2:suite.rc', 'empy:suite.rc', 'template variables'
    ]:
        if section in cli_config:
            cli_config[section].set(['ROSE_ORIG_HOST'], rose_orig_host)
            cli_config[section]['ROSE_ORIG_HOST'].comments = [
                ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING
            ]

    cli_config.comments = [' This file records CLI Options.']
    dumper.dump(cli_config, str(conf_filepath))

    # Merge the opts section of the rose-suite.conf with those set by CLI:
    rose_conf_filepath.touch()
    rose_suite_conf = loader.load(str(rose_conf_filepath))
    rose_suite_conf = add_cylc_install_to_rose_conf_node_opts(
        rose_suite_conf, cli_config
    )
    identify_templating_section(rose_suite_conf)

    dumper(rose_suite_conf, rose_conf_filepath)

    return cli_config, rose_suite_conf


def copy_config_file(
    srcdir: Path,
    rundir: Path,
):
    """Copy the ``rose-suite.conf`` from a workflow source to run directory.

    Args:
        srcdir (pathlib.Path | or str):
            Source Path of Cylc install.
        rundir (pathlib.Path | or str):
            Destination path of Cylc install - the workflow rundir.

    Return:
        True if ``rose-suite.conf`` has been installed.
        False if insufficiant information to install file given.
    """
    srcdir_rose_conf = srcdir / 'rose-suite.conf'
    rundir_rose_conf = rundir / 'rose-suite.conf'

    if not srcdir_rose_conf.is_file():
        return False
    elif rundir_rose_conf.is_file():
        rundir_rose_conf.unlink()
    shutil.copy2(srcdir_rose_conf, rundir_rose_conf)

    return True
