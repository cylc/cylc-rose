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
"""Tests the plugin with Rose suite configurations on the filesystem.

Warning:
   These tests share the same os.environ so may interact.

"""

import os
import pytest

from types import SimpleNamespace
from io import StringIO

from cylc.flow.hostuserutil import get_host
from cylc.rose.utilities import (
    get_cli_opts_node,
    merge_opts,
    merge_rose_cylc_suite_install_conf,
    rose_config_exists,
    rose_config_tree_loader,
    MultipleTemplatingEnginesError
)
from cylc.rose.entry_points import (
    get_rose_vars,
)
from metomi.rose.config import ConfigLoader


HOST = get_host()


def test_rose_config_exists_no_dir(tmp_path):
    assert rose_config_exists(None, SimpleNamespace(
        opt_conf_keys=None, defines=[], define_suites=[])
    ) is False


def test_rose_config_exists_no_rose_suite_conf(tmp_path):
    assert rose_config_exists(
        tmp_path, SimpleNamespace(
            opt_conf_keys=None, defines=[], define_suites=[]
        )
    ) is False


@pytest.mark.parametrize(
    'opts',
    [
        SimpleNamespace(opt_conf_keys='A', defines=[], define_suites=[]),
        SimpleNamespace(
            opt_conf_keys='', defines=['[env]Foo=Bar'], define_suites=[]
        ),
        SimpleNamespace(
            opt_conf_keys='', defines=[], define_suites=['Foo=Bar']
        ),
    ]
)
def test_rose_config_exists_conf_set_by_options(tmp_path, opts):
    assert rose_config_exists(
        tmp_path,
        opts,
    ) is True


def test_rose_config_exists_nonexistant_dir(tmp_path):
    assert rose_config_exists(
        tmp_path / "non-existant-folder", SimpleNamespace(
            opt_conf_keys='', defines=[], define_suites=[]
        )
    ) is False


def test_rose_config_exists_true(tmp_path):
    (tmp_path / "rose-suite.conf").touch()
    assert rose_config_exists(tmp_path, SimpleNamespace()) is True


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
        opt_conf_keys=[], defines=[], define_suites=[]
    )
    if override == 'environment':
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = "gravy"
    else:
        # Prevent externally set environment var breaking tests.
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = ""
    if override == 'CLI':
        options.opt_conf_keys = ["chips"]
    elif override == 'override':
        options.opt_conf_keys = ["chips"]
        options.defines = [
            f"[{section}:suite.rc]Another_Jinja2_var='Variable overridden'"
        ]
    suite_path = rose_config_template(section)
    result = get_rose_vars(
        suite_path, options
    )['template_variables']

    assert result['Another_Jinja2_var'] == exp_ANOTHER_JINJA2_ENV
    assert result['JINJA2_VAR'] == exp_JINJA2_VAR


def test_get_rose_vars_env_section(tmp_path):
    with open(tmp_path / 'rose-suite.conf', 'w+') as testfh:
        testfh.write(
            "[env]\n"
            "DOG_TYPE = Spaniel \n"
        )

    assert (
        get_rose_vars(tmp_path)['env']['DOG_TYPE']
    ) == 'Spaniel'


def test_get_rose_vars_expansions(tmp_path):
    """Check that variables are expanded correctly."""
    os.environ['XYZ'] = "xyz"
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
    rose_vars = get_rose_vars(tmp_path)
    assert rose_vars['template_variables']['LOCAL_ENV'] == 'xyz'
    assert rose_vars['template_variables']['BAR'] == 'ab'
    assert rose_vars['template_variables']['ESCAPED_ENV'] == '$HOME'
    assert rose_vars['template_variables']['INT'] == 42
    assert rose_vars['template_variables']['BOOL'] is True
    assert rose_vars['template_variables']['LIST'] == ["a", 1, True]


def test_get_rose_vars_ROSE_VARS(tmp_path):
    """Test that rose variables are available in the environment section.."""
    (tmp_path / "rose-suite.conf").touch()
    rose_vars = get_rose_vars(tmp_path)
    assert list(rose_vars['env'].keys()) == [
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
        'ROSE_SITE'
    ]


def test_get_rose_vars_jinja2_ROSE_VARS(tmp_path):
    """Test that ROSE_SUITE_VARIABLES are available to jinja2."""
    (tmp_path / "rose-suite.conf").write_text(
        "[jinja2:suite.rc]"
    )
    rose_vars = get_rose_vars(tmp_path)
    assert list(rose_vars['template_variables'][
        'ROSE_SUITE_VARIABLES'
    ].keys()) == [
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
        'ROSE_SITE',
        'ROSE_SUITE_VARIABLES'
    ]


def test_get_rose_vars_fail_if_empy_AND_jinja2(tmp_path):
    """It should raise an error if both empy and jinja2 sections defined."""
    (tmp_path / 'rose-suite.conf').write_text(
        "[jinja2:suite.rc]\n"
        "[empy:suite.rc]\n"
    )
    with pytest.raises(MultipleTemplatingEnginesError):
        get_rose_vars(tmp_path)


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
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = "gravy"
    else:
        # Prevent externally set environment var breaking tests.
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = ""
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
        # Simple cases equivelent to those in doctest:
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
    'state',
    ['!', '!!']
)
def test_cli_defines_ignored_are_ignored(
    state, caplog
):
    opts = SimpleNamespace(
        opt_confs='', defines=[f'[]{state}opts=ignore me'], define_suites=[]
    )
    get_cli_opts_node(opts)
    assert caplog.records[0].message == \
        'CLI opts set to ignored or trigger-ignored will be ignored.'


@pytest.mark.parametrize(
    'opt_confs, defines, define_suites, expect',
    [
        # Basic simple test
        ('A B', ['[env]FOO=BAR'], ['QUX=BAZ'], (
            "!opts=A B\n"
            "\n[env]\n"
            "FOO=BAR\n"
            f"ROSE_ORIG_HOST={HOST}\n"
            "\n[jinja2:suite.rc]\n"
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
                "\n[jinja2:suite.rc]\n"
                "!BAZ=Zaphod\n"
                "!!QUX=Ford\n"
                f"ROSE_ORIG_HOST={HOST}\n"
            )
        )
    ]
)
def test_get_cli_opts_node(opt_confs, defines, define_suites, expect):
    opts = SimpleNamespace(
        opt_conf_keys=opt_confs,
        defines=defines,
        define_suites=define_suites
    )
    loader = ConfigLoader()
    expect = loader.load(StringIO(expect))
    result = get_cli_opts_node(opts)
    for item in ['env', 'jinja2:suite.rc', 'opts']:
        assert result[item] == expect[item]


@pytest.mark.parametrize(
    'old, new, expect',
    [
        # An example with only opts:
        ('opts=a b c', 'opts=c d e', '\nopts=a b c d e\n'),
        # An example with lots of options:
        (
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            'opts=B C\n[env]\nFOO=Pinhoe\n[jinja2:suite.rc]\nBAR=Broadclyst',
            'opts=A B C\n[env]\nFOO=Pinhoe\n[jinja2:suite.rc]\nBAR=Broadclyst'
        ),
        # An example with no old opts:
        (
            '',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree'
        ),
        # An example with no new opts:
        (
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree',
            '',
            'opts=A B\n[env]\nFOO=Whipton\n[jinja2:suite.rc]\nBAR=Heavitree'
        )
    ]
)
def test_merge_rose_cylc_suite_install_conf(old, new, expect):
    loader = ConfigLoader()
    old = loader.load(StringIO(old))
    new = loader.load(StringIO(new))
    assert loader.load(StringIO(expect)) == \
        merge_rose_cylc_suite_install_conf(old, new)
