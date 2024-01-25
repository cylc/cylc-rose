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

"""Tests the plugin with Rose suite configurations on the filesystem."""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from cylc.flow.hostuserutil import get_host
from metomi.rose.config import ConfigLoader
import pytest
from pytest import param

from cylc.rose.entry_points import (
    process_config,
    load_rose_config,
)
from cylc.rose.utilities import (
    MultipleTemplatingEnginesError,
    get_cli_opts_node,
    merge_opts,
    merge_rose_cylc_suite_install_conf,
    rose_config_exists,
    rose_config_tree_loader,
)

HOST = get_host()


def node_stripper(node):
    """strip a node and all sub-nodes of non-value items.

    Examples:

    """
    result = {}
    if hasattr(node, 'value'):
        if isinstance(node.value, dict):
            for key, value in node.value.items():
                result[key] = node_stripper(value)
        else:
            return node.value
    return result


def test_node_stripper():
    result = node_stripper(
        SimpleNamespace(
            value={'foo': SimpleNamespace(value='bar', state='wurble')},
            comment='This should get binned.'
        )
    )
    assert result == {'foo': 'bar'}


def test_rose_config_exists_no_rose_suite_conf(tmp_path):
    assert not rose_config_exists(tmp_path)


def test_rose_config_exists_nonexistant_dir(tmp_path):
    assert not rose_config_exists(tmp_path / "non-existant-folder")


def test_rose_config_exists_true(tmp_path):
    (tmp_path / "rose-suite.conf").touch()
    assert rose_config_exists(tmp_path)


@pytest.fixture
def rose_config_template(tmp_path, scope='module'):
    def wrapped_function(section):
        """Fixture which returns a tmp_path containing a rose config tree.

        uses ``wrapped_function`` to allow passing either "empy" or "jinja2"
        section types.

        Creates:
        .
        `--tmp_path
            |-- rose-suite.conf
            `-- opt
                |-- rose-suite-gravy.conf
                `-- rose-suite-chips.conf
        """
        with open(tmp_path / 'rose-suite.conf', 'w+') as testfh:
            # The [env] section is there to make sure I don't load it with
            # the jinja2 method.
            testfh.write(
                "[env]\n"
                "Dontwantthis_ENV_VAR=Jelly\n"
                f"[{section}:suite.rc]\n"
                "JINJA2_VAR=64\n"
                'Another_Jinja2_var="Defined in config"\n'
            )

        opt_dir = tmp_path / 'opt'
        opt_dir.mkdir()
        with open(opt_dir / 'rose-suite-gravy.conf', 'w+') as testfh:
            testfh.write(
                f"[{section}:suite.rc]\n"
                "JINJA2_VAR=42\n"
                "Another_Jinja2_var='Optional config picked from env var'\n"
            )

        with open(opt_dir / 'rose-suite-chips.conf', 'w+') as testfh:
            testfh.write(
                f"[{section}:suite.rc]\n"
                "JINJA2_VAR=99\n"
                "Another_Jinja2_var='Optional config picked from CLI'\n"
            )
        return tmp_path
    return wrapped_function


@pytest.mark.parametrize(
    'override, section, exp_ANOTHER_JINJA2_ENV, exp_JINJA2_VAR',
    [
        (None, 'jinja2', 'Defined in config', 64),
        (None, 'empy', 'Defined in config', 64),
        ('environment', 'jinja2', 'Optional config picked from env var', 42),
        ('CLI', 'jinja2', 'Optional config picked from CLI', 99),
        ('environment', 'empy', 'Optional config picked from env var', 42),
        ('CLI', 'empy', 'Optional config picked from CLI', 99),
        ('override', 'jinja2', 'Variable overridden', 99),
        ('override', 'empy', 'Variable overridden', 99)
    ]
)
def test_get_rose_vars(
    monkeypatch,
    rose_config_template,
    override,
    section,
    exp_ANOTHER_JINJA2_ENV,
    exp_JINJA2_VAR
):
    """Test reading of empy or jinja2 vars

    Scenarios tested:
        - Read in a basic rose-suite.conf file. Ensure we don't return env,
          just jinja2/empy.
        - Get optional config name from an environment variable.
        - Get optional config name from command line option.
        - Get optional config name from an explicit over-ride string.
    """
    options = SimpleNamespace(
        opt_conf_keys=[], defines=[], rose_template_vars=[]
    )
    if override == 'environment':
        monkeypatch.setenv('ROSE_SUITE_OPT_CONF_KEYS', 'gravy')
    else:
        # Prevent externally set environment var breaking tests.
        monkeypatch.setenv('ROSE_SUITE_OPT_CONF_KEYS', '')
    if override == 'CLI':
        options.opt_conf_keys = ["chips"]
    elif override == 'override':
        options.opt_conf_keys = ["chips"]
        options.defines = [
            f"[{section}:suite.rc]Another_Jinja2_var='Variable overridden'"
        ]
    suite_path = rose_config_template(section)
    config_tree = load_rose_config(
        suite_path, options
    )
    template_variables = (
        process_config(config_tree)['template_variables']
    )
    assert template_variables['Another_Jinja2_var'] == exp_ANOTHER_JINJA2_ENV
    assert template_variables['JINJA2_VAR'] == exp_JINJA2_VAR


def test_get_rose_vars_env_section(tmp_path):
    with open(tmp_path / 'rose-suite.conf', 'w+') as testfh:
        testfh.write(
            "[env]\n"
            "DOG_TYPE = Spaniel \n"
        )

    config_tree = load_rose_config(tmp_path)
    environment_variables = process_config(config_tree)['env']
    assert environment_variables['DOG_TYPE'] == 'Spaniel'


def test_get_rose_vars_expansions(monkeypatch, tmp_path):
    """Check that variables are expanded correctly."""
    monkeypatch.setenv('XYZ', 'xyz')
    (tmp_path / "rose-suite.conf").write_text(
        "[env]\n"
        "FOO=a\n"
        "[jinja2:suite.rc]\n"
        'BAR="${FOO}b"\n'
        'LOCAL_ENV="$XYZ"\n'
        'ESCAPED_ENV="\\$HOME"\n'
        "INT=42\n"
        "BOOL=True\n"
        'LIST=["a", 1, True]\n'
    )
    config_tree = load_rose_config(tmp_path)
    template_variables = (
        process_config(config_tree)['template_variables']
    )
    assert template_variables['LOCAL_ENV'] == 'xyz'
    assert template_variables['BAR'] == 'ab'
    assert template_variables['ESCAPED_ENV'] == '$HOME'
    assert template_variables['INT'] == 42
    assert template_variables['BOOL'] is True
    assert template_variables['LIST'] == ["a", 1, True]


def test_get_rose_vars_ROSE_VARS(tmp_path):
    """Test that rose variables are available in the environment section.."""
    (tmp_path / "rose-suite.conf").touch()
    config_tree = load_rose_config(tmp_path)
    environment_variables = (
        process_config(config_tree)['env']
    )
    assert sorted(environment_variables) == sorted([
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
    ])


def test_get_rose_vars_jinja2_ROSE_VARS(tmp_path):
    """Test that ROSE_SUITE_VARIABLES are available to jinja2."""
    (tmp_path / "rose-suite.conf").write_text(
        "[jinja2:suite.rc]"
    )
    config_tree = load_rose_config(tmp_path)
    template_variables = (
        process_config(config_tree)['template_variables']
    )
    assert sorted(
        template_variables['ROSE_SUITE_VARIABLES']
    ) == sorted([
        'ROSE_VERSION',
        'ROSE_ORIG_HOST',
        'ROSE_SUITE_VARIABLES'
    ])


def test_get_rose_vars_fail_if_empy_AND_jinja2(tmp_path):
    """It should raise an error if both empy and jinja2 sections defined."""
    (tmp_path / 'rose-suite.conf').write_text(
        "[jinja2:suite.rc]\n"
        "[empy:suite.rc]\n"
    )
    config_tree = load_rose_config(tmp_path)
    with pytest.raises(MultipleTemplatingEnginesError):
        process_config(config_tree)


@pytest.mark.parametrize(
    'override, section, exp_ANOTHER_JINJA2_ENV, exp_JINJA2_VAR, opts_format',
    [
        (None, 'jinja2', '"Defined in config"', 64, 'list'),
        (None, 'empy', '"Defined in config"', 64, 'list'),
        (
            'environment', 'jinja2', "'Optional config picked from env var'",
            42, 'list'
        ),
        ('CLI', 'jinja2', "'Optional config picked from CLI'", 99, 'list'),
        (
            'environment', 'empy',
            "'Optional config picked from env var'", 42, 'list'
        ),
        ('CLI', 'empy', "'Optional config picked from CLI'", 99, 'list'),
        ('override', 'jinja2', 'Variable overridden', 99, 'list'),
        ('override', 'empy', 'Variable overridden', 99, 'list'),
        (None, 'jinja2', '"Defined in config"', 64, 'str'),
        (None, 'empy', '"Defined in config"', 64, 'str'),
        (
            'environment', 'jinja2', "'Optional config picked from env var'",
            42, 'str'
        ),
        ('CLI', 'jinja2', "'Optional config picked from CLI'", 99, 'str'),
        (
            'environment', 'empy', "'Optional config picked from env var'",
            42, 'str'
        ),
        ('CLI', 'empy', "'Optional config picked from CLI'", 99, 'str'),
        ('override', 'jinja2', 'Variable overridden', 99, 'str'),
        ('override', 'empy', 'Variable overridden', 99, 'str')
    ]
)
def test_rose_config_tree_loader(
    monkeypatch,
    rose_config_template,
    override,
    section,
    exp_ANOTHER_JINJA2_ENV,
    exp_JINJA2_VAR,
    opts_format
):
    """Test reading of empy or jinja2 vars

    Scenarios tested:
        - Read in a basic rose-suite.conf file. Ensure we don't return env,
          just jinja2/empy.
        - Get optional config name from an environment variable.
        - Get optional config name from command line option.
        - Get optional config name from an explicit over-ride string.
    """
    options = None
    if override == 'environment':
        monkeypatch.setenv('ROSE_SUITE_OPT_CONF_KEYS', 'gravy')
    else:
        # Prevent externally set environment var breaking tests.
        monkeypatch.setenv('ROSE_SUITE_OPT_CONF_KEYS', '')
    if opts_format == 'list':
        conf_keys = ['chips']
    else:
        conf_keys = 'chips'
    if override == 'CLI':
        options = SimpleNamespace()
        options.opt_conf_keys = conf_keys
    if override == 'override':
        options = SimpleNamespace()
        options.opt_conf_keys = conf_keys
        options.defines = [
            f"[{section}:suite.rc]Another_Jinja2_var=Variable overridden"
        ]

    result = rose_config_tree_loader(
        rose_config_template(section), options
    ).node.value[section + ':suite.rc'].value
    results = {
        'Another_Jinja2_var': result['Another_Jinja2_var'].value,
        'JINJA2_VAR': result['JINJA2_VAR'].value
    }
    expected = {
        'Another_Jinja2_var': f'{exp_ANOTHER_JINJA2_ENV}',
        'JINJA2_VAR': f'{exp_JINJA2_VAR}'
    }
    assert results == expected


@pytest.mark.parametrize(
    'expect, file, opts',
    [
        param(
            {'template variables': {'FOO': '"Bar"'}},
            '',
            {'rose_template_vars': ['FOO="Bar"']},
            id="rose_template_vars-set-by--S"
        ),
        param(
            {'template variables': {'FOO': 'Bar'}},
            '',
            {'rose_template_vars': ['FOO=Bar']},
            id="rose_template_vars-set-by--S-(unquoted-will-fail-later)"
        ),
        param(
            {'jinja2:suite.rc': {'FOO': '"Bar"'}},
            '[jinja2:suite.rc]\n',
            {'rose_template_vars': ['FOO="Bar"']},
            id="rose_template_vars-set-by--S-(jinja2 already set in file)"
        ),
        param(
            {'empy:suite.rc': {'FOO': '"Bar"'}},
            '[empy:suite.rc]\n',
            {'rose_template_vars': ['FOO="Bar"']},
            id="rose_template_vars-set-by--S-(empy already set in file)"
        ),
        param(
            {'Any Old Section': {'FOO': '"Bar"'}},
            '',
            {'defines': ['[Any Old Section]FOO="Bar"']},
            id="defines-set-by--D"
        ),
    ]
)
def test_rose_config_tree_loader_CLI_handling(tmp_path, expect, file, opts):
    """Test interaction of config tree loader with -S and -D.
    """
    source = tmp_path
    (source / 'rose-suite.conf').write_text(file)
    opts = SimpleNamespace(**opts)
    tree = rose_config_tree_loader(source, opts)
    assert node_stripper(tree.node) == expect


@pytest.fixture
def rose_fileinstall_config_template(tmp_path, scope='module'):
    def wrapped_function(section):
        """Fixture which returns a tmp_path containing a rose config tree.

        uses ``wrapped_function`` to allow passing either "empy" or "jinja2"
        section types.

        Creates:
        .
        `--tmp_path
            |-- rose-suite.conf
            `-- opt
                |-- rose-suite-gravy.conf
                `-- rose-suite-chips.conf
        """
        with open(tmp_path / 'rose-suite.conf', 'w+') as testfh:
            # The [env] section is there to make sure I don't load it with
            # the jinja2 method.
            testfh.write(
                "[file]\n"
                "Dontwantthis_ENV_VAR=Jelly\n"
                f"[{section}:suite.rc]\n"
                "JINJA2_VAR=64\n"
                "Another_Jinja2_var=Defined in config\n"
            )
        return tmp_path
    return wrapped_function


@pytest.mark.parametrize(
    'defines_opts, env_opts, opt_conf_keys, expected',
    [
        # Simple cases equivalent to those in doctest:
        ('a', None, 'c', 'a c'),
        ('a', 'b', '', 'a b'),
        ('a', 'b', 'c', 'a b c'),
        # Simple case, inconvienent to do in doctest:
        ('', 'b', 'c', 'b c'),
        # opt_conf_keys contains multiple items:
        ('a', 'b', 'c d', 'a b c d'),
        ('a', 'b', ['c', 'd'], 'a b c d'),
        # test options with overlapping sets:
        ('a b', 'b c', 'c d', 'a b c d'),
        # test options with repetition (not exhaustive - don't need to
        # duplicate test_merge_opts).
        ('a b a', 'c d c', 'e f e', 'b a d c f e'),
        ('a b a', 'b c b', 'c d c', 'a b d c'),
    ]
)
def test_merge_opts(
    defines_opts, env_opts, opt_conf_keys, expected, monkeypatch
):
    """It merges options in the correct order:

    1. defines
    2. env
    3. opt-conf-keys
    """
    # Set up a fake ConfigNode.
    conf = SimpleNamespace()
    conf.value = defines_opts
    conf = {'opts': conf}

    # Fake the ROSE_SUITE_OPT_CONF_KEYS environment variable.
    if env_opts is not None:
        monkeypatch.setenv('ROSE_SUITE_OPT_CONF_KEYS', env_opts)

    assert merge_opts(conf, opt_conf_keys) == expected


@pytest.mark.parametrize(
    'opt_confs, defines, rose_template_vars, expect',
    [
        # Basic simple test
        ('A B', ['[env]FOO=BAR'], ['QUX=BAZ'], (
            "!opts=A B\n"
            "\n[env]\n"
            "FOO=BAR\n"
            f"ROSE_ORIG_HOST={HOST}\n"
            "\n[template variables]\n"
            "QUX=BAZ\n"
            f"ROSE_ORIG_HOST={HOST}"
        )),
        # Check handling of ignored & trigger ignored items
        (
            '',
            ['[env]!FOO=Arthur', '[env]!!BAR=Trillian'],
            ['!BAZ=Zaphod', '!!QUX=Ford'],
            (
                "opts=''#\n"
                "\n[env]\n"
                "!FOO=Arthur\n"
                "!!BAR=Trillian\n"
                f"ROSE_ORIG_HOST={HOST}\n"
                "\n[template variables]\n"
                "!BAZ=Zaphod\n"
                "!!QUX=Ford\n"
                f"ROSE_ORIG_HOST={HOST}\n"
            )
        )
    ]
)
def test_get_cli_opts_node(opt_confs, defines, rose_template_vars, expect):
    opts = SimpleNamespace(
        opt_conf_keys=opt_confs,
        defines=defines,
        rose_template_vars=rose_template_vars
    )
    loader = ConfigLoader()
    expect = loader.load(StringIO(expect))
    result = get_cli_opts_node(Path('no/such/dir'), opts)
    for item in ['env', 'template variables', 'opts']:
        assert result[item] == expect[item]


@pytest.mark.parametrize(
    'old, new, expect',
    [
        # An example with only opts:
        param(
            'opts=a b c', 'opts=c d e', '\nopts=a b c d e\n',
            id='only opts'
        ),
        # An example with lots of options:
        param(
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            'opts=B C\n[env]\nFOO=Pinhoe\n[jinja2:suite.rc]\nBAR=Broadclyst',
            'opts=A B C\n[env]\nFOO=Pinhoe\n[jinja2:suite.rc]\nBAR=Broadclyst',
            id='lots of options'
        ),
        # An example with updated template variables:
        param(
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Ottery',
            'opts=B C\n[env]\nFOO=Pinhoe\n[template variables]\nBAR=Whipton',
            'opts=A B C\n[env]\nFOO=Pinhoe\n[template variables]\nBAR=Whipton',
            id='changed template vars'
        ),
        # An example with no old opts:
        param(
            '',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            id='no old options'
        ),
        # An example with no new opts:
        param(
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            '',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            id='no new opts'
        )
    ]
)
def test_merge_rose_cylc_suite_install_conf(old, new, expect):
    loader = ConfigLoader()
    old = loader.load(StringIO(old))
    new = loader.load(StringIO(new))
    assert (loader.load(StringIO(expect)) ==
            merge_rose_cylc_suite_install_conf(old, new)
            )
