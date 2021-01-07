# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

from cylc.rose.rose import (
    get_rose_vars_from_config_tree,
    rose_config_exists,
    rose_config_tree_loader,
    rose_fileinstall
)


def test_rose_config_exists_no_dir(tmp_path):
    assert rose_config_exists(None) is False


def test_rose_config_exists_no_rose_suite_conf(tmp_path):
    assert rose_config_exists(tmp_path) is False


def test_rose_config_exists_nonexistant_dir(tmp_path):
    assert rose_config_exists(tmp_path / "non-existant-folder") is False


def test_rose_config_exists_true(tmp_path):
    (tmp_path / "rose-suite.conf").touch()
    assert rose_config_exists(tmp_path) is True


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
def test_get_rose_vars_from_config_tree(
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
    options = None
    if override == 'environment':
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = "gravy"
    else:
        # Prevent externally set environment var breaking tests.
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = ""
    if override == 'CLI':
        options = SimpleNamespace()
        options.opt_conf_keys = ["chips"]
    if override == 'override':
        options = SimpleNamespace()
        options.opt_conf_keys = ["chips"]
        options.defines = [
            f"[{section}:suite.rc]Another_Jinja2_var='Variable overridden'"
        ]

    result = get_rose_vars_from_config_tree(
        rose_config_template(section), options
    )['template_variables']

    assert result['Another_Jinja2_var'] == exp_ANOTHER_JINJA2_ENV
    assert result['JINJA2_VAR'] == exp_JINJA2_VAR


def test_get_rose_vars_from_config_tree_env_section(tmp_path):
    with open(tmp_path / 'rose-suite.conf', 'w+') as testfh:
        testfh.write(
            "[env]\n"
            "DOG_TYPE = Spaniel \n"
        )

    assert (
        get_rose_vars_from_config_tree(tmp_path)['env']['DOG_TYPE']
    ) == 'Spaniel'


def test_get_rose_vars_from_config_tree_expansions(tmp_path):
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
    rose_vars = get_rose_vars_from_config_tree(tmp_path)
    assert rose_vars['template_variables']['LOCAL_ENV'] == 'xyz'
    assert rose_vars['template_variables']['BAR'] == 'ab'
    assert rose_vars['template_variables']['ESCAPED_ENV'] == '$HOME'
    assert rose_vars['template_variables']['INT'] == 42
    assert rose_vars['template_variables']['BOOL'] is True
    assert rose_vars['template_variables']['LIST'] == ["a", 1, True]


def test_get_rose_vars_from_config_tree_ROSE_VARS(tmp_path):
    """Test that rose variables are available in the environment section.."""
    (tmp_path / "rose-suite.conf").touch()
    rose_vars = get_rose_vars_from_config_tree(tmp_path)
    assert list(rose_vars['env'].keys()) == [
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
        'ROSE_SITE'
    ]


def test_get_rose_vars_from_config_tree_jinja2_ROSE_VARS(tmp_path):
    """Test that ROSE_SUITE_VARIABLES are available to jinja2."""
    (tmp_path / "rose-suite.conf").write_text(
        "[jinja2:suite.rc]"
    )
    rose_vars = get_rose_vars_from_config_tree(tmp_path)
    assert list(rose_vars['template_variables'][
        'ROSE_SUITE_VARIABLES'
    ].keys()) == [
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
        'ROSE_SITE',
        'ROSE_SUITE_VARIABLES'
    ]


def test_get_rose_vars_from_config_tree_fail_if_empy_AND_jinja2(tmp_path):
    """It should raise an error if both empy and jinja2 sections defined."""
    (tmp_path / 'rose-suite.conf').write_text(
        "[jinja2:suite.rc]\n"
        "[empy:suite.rc]\n"
    )
    from cylc.rose.rose import MultipleTemplatingEnginesError
    with pytest.raises(MultipleTemplatingEnginesError):
        get_rose_vars_from_config_tree(tmp_path)


@pytest.mark.parametrize(
    'override, section, exp_ANOTHER_JINJA2_ENV, exp_JINJA2_VAR',
    [
        (None, 'jinja2', '"Defined in config"', 64),
        (None, 'empy', '"Defined in config"', 64),
        ('environment', 'jinja2', "'Optional config picked from env var'", 42),
        ('CLI', 'jinja2', "'Optional config picked from CLI'", 99),
        ('environment', 'empy', "'Optional config picked from env var'", 42),
        ('CLI', 'empy', "'Optional config picked from CLI'", 99),
        ('override', 'jinja2', 'Variable overridden', 99),
        ('override', 'empy', 'Variable overridden', 99)
    ]
)
def test_rose_config_tree_loader(
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
    options = None
    if override == 'environment':
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = "gravy"
    else:
        # Prevent externally set environment var breaking tests.
        os.environ['ROSE_SUITE_OPT_CONF_KEYS'] = ""
    if override == 'CLI':
        options = SimpleNamespace()
        options.opt_conf_keys = ["chips"]
    if override == 'override':
        options = SimpleNamespace()
        options.opt_conf_keys = ["chips"]
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


def test_rose_fileinstall(tmp_path):
    """Check that we can install files specified in a rose-suite.conf."""
    othersource_dir = tmp_path / "sources"
    workflow_dir = tmp_path / "workflow"
    destination_dir = tmp_path / "destination"
    for dir_ in [othersource_dir, workflow_dir, destination_dir]:
        dir_.mkdir()

    york_content = "Now is the winter of our discontent..."
    lancaster_content = "Thus did ever rebellion find rebuke."
    york = othersource_dir / "York"
    lancaster = othersource_dir / "Lancaster"
    (york).write_text(york_content)
    (lancaster).write_text(lancaster_content)

    red = destination_dir / "Red"
    white = destination_dir / "White"

    with open(workflow_dir / 'rose-suite.conf', 'w+') as testfh:
        # The [env] section is there to make sure I don't load it with
        # the jinja2 method.
        testfh.write(
            "[file:White]\n"
            f"source={str(york)}\n"
            "[file:Red]\n"
            f"source={str(lancaster)}\n"
        )

    rose_fileinstall(dir_=str(workflow_dir), dest_root=str(destination_dir))

    assert red.read_text() == lancaster.read_text()
    assert white.read_text() == york.read_text()
