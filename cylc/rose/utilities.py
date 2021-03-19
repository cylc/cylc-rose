# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC SUITE ENGINE.
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
"""Cylc support for reading and interpreting ``rose-suite.conf`` workflow
configuration files.
"""

import os
from pathlib import Path
import re
import shlex
from typing import TYPE_CHECKING, Union

from cylc.flow.hostuserutil import get_host
from cylc.flow import LOG
from cylc.rose.jinja2_parser import Parser
from metomi.rose import __version__ as ROSE_VERSION
from metomi.isodatetime.datetimeoper import DateTimeOperator
from metomi.rose.config import ConfigDumper, ConfigNodeDiff, ConfigNode
from metomi.rose.config_processor import ConfigProcessError
from metomi.rose.env import env_var_process, UnboundEnvironmentVariableError
from metomi.rose.resource import ResourceLocator

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Options


class MultipleTemplatingEnginesError(Exception):
    ...


def get_rose_vars_from_config_node(config, config_node, environ):
    """Load template variables from a Rose config node.

    This uses only the provided config node and environment variables
    - there is no system interaction.

    Args:
        config (dict):
            Object which will be populated with the results.
        config_node (metomi.rose.config.ConfigNode):
            Configuration node representing the Rose suite configuration.
        environ (dict):
            Dictionary of environment variables

    """
    templating = None
    sections = {'jinja2:suite.rc', 'empy:suite.rc', 'template variables'}

    # Don't allow multiple templating sections.
    defined_sections = sections.intersection(set(config_node.value))
    if len(defined_sections) > 1:
        raise MultipleTemplatingEnginesError(
            "You should not define more than one templating section. "
            f"You defined:\n\t{'; '.join(defined_sections)}"
        )
    elif len(defined_sections) == 1:
        templating, = defined_sections
        if templating != 'template variables':
            config['templating_detected'] = templating.replace(':suite.rc', '')
        else:
            config['templating_detected'] = templating

    # Create env section if it doesn't already exist.
    if 'env' not in config_node.value:
        config_node.set(['env'])

    # Get Values for standard ROSE variables (ROSE_ORIG_HOST and ROSE_SITE).
    rose_orig_host = get_host()
    rose_site = ResourceLocator().get_conf().get_value(['site'], '')

    # For each section process variables and add standard variables.
    for section in ['env', templating]:
        if section not in config_node.value:
            continue

        # Add standard ROSE_VARIABLES
        config_node[section].set(['ROSE_SITE'], rose_site)
        config_node[section].set(['ROSE_VERSION'], ROSE_VERSION)
        config_node[section].set(['ROSE_ORIG_HOST'], rose_orig_host)

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
    if 'env' in config_node.value:
        config['env'] = {
            item[0][1]: item[1].value for item in
            config_node.value['env'].walk()
        }
    if templating in config_node.value:
        config['template_variables'] = {
            item[0][1]: item[1].value for item in
            config_node.value[templating].walk()
        }
    elif 'template variables' in config_node.value:
        config['template_variables'] = {
            item[0][1]: item[1].value for item in
            config_node.value['template variables'].walk()
        }

    # Add the entire config to ROSE_SUITE_VARIABLES to allow for programatic
    # access.
    if templating is not None:
        parser = Parser()
        for key, value in config['template_variables'].items():
            # The special variables are already Python variables.
            if key not in ['ROSE_ORIG_HOST', 'ROSE_VERSION', 'ROSE_SITE']:
                try:
                    config['template_variables'][key] = (
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

    # Add ROSE_SUITE_VARIABLES to config of templating engines in use.
    if templating is not None:
        config['template_variables'][
            'ROSE_SUITE_VARIABLES'] = config['template_variables']


def rose_config_exists(
    srcdir: Union[Path, str, None], opts: 'Options'
) -> bool:
    """Do opts or srcdir contain a rose config?

    Args:
        srcdir: location to test.
        opts: Cylc Rose options, which might contain config items.

    Returns:
        True if a ``rose-suite.conf`` exists, or option config items have
        been set.
    """
    # Return false if source dir doesn't exist.
    if srcdir is None:
        return False

    # If _any_ of the following are true we want to return True.
    if (
        Path(srcdir, 'rose-suite.conf').is_file() or
        opts and opts.opt_conf_keys or
        opts and opts.defines or
        opts and opts.define_suites
    ):
        return True
    return False


def rose_config_tree_loader(srcdir=None, opts=None):
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
    opt_conf_keys_env = os.getenv("ROSE_SUITE_OPT_CONF_KEYS")
    if opt_conf_keys_env:
        opt_conf_keys += shlex.split(opt_conf_keys_env)

    # ... or as command line options
    if opts and 'opt_conf_keys' in dir(opts) and opts.opt_conf_keys:
        if isinstance(opts.opt_conf_keys, str):
            opt_conf_keys += opts.opt_conf_keys.split()
        elif isinstance(opts.opt_conf_keys, list):
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

    return config_tree


def merge_rose_cylc_suite_install_conf(old, new):
    """Merge old and new ``rose-suite-cylc-install.conf`` configs nodes.

    Opts are merged separately to allow special behaviour.
    The rest is merged using ConfigNodeDiff.

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


def get_cli_opts_node(opts=None):
    """Create a ConfigNode representing options set on the command line.

    Args:
        opts (CylcOptionParser object):
            Object with values from the command line.

    Returns:
        Rose ConfigNode.

    Example:
        >>> from types import SimpleNamespace
        >>> opts = SimpleNamespace(
        ...     opt_conf_keys='A B',
        ...     defines=["[env]FOO=BAR"],
        ...     define_suites=["QUX=BAZ"]
        ... )
        >>> node = get_cli_opts_node(opts)
        >>> node['opts']
        {'value': 'A B', 'state': '!', 'comments': []}
        >>> node['env']['FOO']
        {'value': 'BAR', 'state': '', 'comments': []}
        >>> node['jinja2:suite.rc']['QUX']
        {'value': 'BAZ', 'state': '', 'comments': []}
    """
    # Unpack info we want from opts:
    opt_conf_keys = []
    defines = []
    suite_defines = []
    if opts and 'opt_conf_keys' in dir(opts):
        opt_conf_keys = opts.opt_conf_keys
    if opts and 'defines' in dir(opts):
        defines = opts.defines
    if opts and 'define_suites' in dir(opts):
        suite_defines = opts.define_suites

    # Construct new ouput based on optional Configs:
    newconfig = ConfigNode()

    # For each __define__ determine whether it is an env or template define.
    for define in defines:
        match = re.match(
                (
                    r'^\[(?P<key1>.*)\](?P<state>!{0,2})'
                    r'(?P<key2>.*)\s*=\s*(?P<value>.*)'
                ),
                define
            ).groupdict()
        if match['key1'] == '' and match['state'] in ['!', '!!']:
            LOG.warning(
                'CLI opts set to ignored or trigger-ignored will be ignored.'
            )
        else:
            newconfig.set(
                keys=[match['key1'], match['key2']],
                value=match['value'],
                state=match['state']
            )

    # For each __suite define__ add define.
    for define in suite_defines:
        # For now just assuming that we just support Jinja2 - after I've
        # Implemented the fully template-engine neutral template variables
        # section this should be a moot point.
        match = re.match(
            r'(?P<state>!{0,2})(?P<key>.*)\s*=\s*(?P<value>.*)', define
        ).groupdict()
        newconfig.set(
            keys=['jinja2:suite.rc', match['key']],
            value=match['value'],
            state=match['state']
        )

    # Specialised treatement of optional configs.
    if 'opts' not in newconfig:
        newconfig['opts'] = ConfigNode()
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
        >>> import os; os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = 'bet'
        >>> merge_opts(conf, '')
        'aleph bet'

        Merge all three options.
        >>> merge_opts(conf, 'gimmel')
        'aleph bet gimmel'
    """
    all_opt_conf_keys = []
    if 'opts' in config:
        all_opt_conf_keys.append(config['opts'].value)
    if "ROSE_SUITE_OPT_CONF_KEYS" in os.environ:
        all_opt_conf_keys.append(os.environ["ROSE_SUITE_OPT_CONF_KEYS"])
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
    for index, item in enumerate(reversed(opts.split())):
        if item not in seen_once:
            seen_once.append(item)

    return ' '.join(reversed(seen_once))


def dump_rose_log(rundir, node):
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
        print_format='%Y%m%dT%H%M%S%Z'
    )
    rel_path = f'log/conf/{timestamp}-rose-suite.conf'
    fpath = rundir / rel_path
    fpath.parent.mkdir(exist_ok=True, parents=True)
    dumper.dump(node, str(fpath))
    return rel_path


def paths_to_pathlib(paths):
    """Convert paths to pathlib
    """
    return [
        Path(path) if path is not None
        else None
        for path in paths
    ]
