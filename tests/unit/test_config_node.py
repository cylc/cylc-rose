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

"""Tests the plugin with Rose suite configurations via the Python API."""

from textwrap import dedent
from types import SimpleNamespace

from metomi.isodatetime.datetimeoper import DateTimeOperator
from metomi.rose import __version__ as ROSE_VERSION
from metomi.rose.config import ConfigNode
from metomi.rose.config_tree import ConfigTree
from metomi.rose.config_processor import ConfigProcessError
import pytest

from cylc.rose.utilities import (
    ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING,
    add_cylc_install_to_rose_conf_node_opts,
    deprecation_warnings,
    dump_rose_log,
    process_config,
    id_templating_section,
    identify_templating_section,
    retrieve_installed_cli_opts,
)


def test_blank():
    """It should provide only standard vars for a blank config."""
    ret = process_config(ConfigTree(), {})
    assert set(ret.keys()) == {
        'template_variables', 'templating_detected', 'env'
    }
    assert set(ret['env'].keys()) == {
        'ROSE_ORIG_HOST',
        'ROSE_VERSION',
    }


def test_invalid_templatevar():
    """It should wrap eval errors as something more informative."""
    tree = ConfigTree()
    node = ConfigNode()
    node.set(['jinja2:suite.rc', 'X'], 'Y')
    tree.node = node
    with pytest.raises(ConfigProcessError):
        process_config(tree, {})


def test_get_plugin_result__unbound_env_var(caplog):
    """It should fail if variable unset in environment.
    """
    tree = ConfigTree()
    node = ConfigNode()
    node.set(['env', 'X'], '${MYVAR}')
    tree.node = node
    with pytest.raises(ConfigProcessError) as exc:
        process_config(tree, {})
    assert exc.match('env=X: MYVAR: unbound variable')


@pytest.fixture
def override_version_vars(caplog, scope='module'):
    """Set up config tree and pass to process_config

    Yields:
        node: The node after manipulation.
        message: A string representing the caplog output.
    """
    tree = ConfigTree()
    node = ConfigNode()
    node.set(['template variables', 'ROSE_VERSION'], 99)
    node.set(['template variables', 'CYLC_VERSION'], 101)
    tree.node = node
    process_config(tree, {})
    message = '\n'.join([i.message for i in caplog.records])
    yield (node, message)


def test_get_vars_from_config_node__ignores_user_ROSE_VERSION(
    override_version_vars
):
    """It should warn that user ROSE_VERSION will be changed."""
    assert f'ROSE_VERSION will be: {ROSE_VERSION}' in override_version_vars[1]


def test_get_vars_from_config_node__sets_right_ROSE_VERSION(
    override_version_vars
):
    """It should replace user ROSE_VERSION with rose.__version__"""
    assert override_version_vars[
        0]['template variables']['ROSE_VERSION'].value == ROSE_VERSION


def test_get_vars_from_config_node__ignores_user_CYLC_VERSION(
    override_version_vars
):
    """It should warn that user CYLC_VERSION will be unset."""
    assert 'CYLC_VERSION will be: set by Cylc' in override_version_vars[1]


def test_get_vars_from_config_node__unsets_CYLC_VERSION(
    override_version_vars
):
    """It should tell user what cylc.__version__ is."""
    assert 'CYLC_VERSION' not in override_version_vars[0]['template variables']


@pytest.mark.parametrize(
    'rose_conf, cli_conf, expect',
    [
        ({}, {}, '(cylc-install)'),
        # It is not given rose_node with 'opts': adds (cylc-install) to opts:
        ({}, {'opts': ''}, '(cylc-install)'),
        # opts ignored in the config
        ({'!opts': ''}, {}, '(cylc-install)'),
        # It is given empty 'opts' rose_node - adds (cylc-install) to opts:
        ({'opts': ''}, {'opts': ''}, '(cylc-install)'),
        # It add (cylc-install) to existing rose_conf keys:
        ({'opts': 'foo bar'}, {'opts': ''}, 'foo bar (cylc-install)'),
        # It add (cylc-install) to CLI set keys:
        ({'opts': ''}, {'opts': 'baz qux'}, 'baz qux (cylc-install)'),
        # It add (cylc-install) to existing rose_conf keys & CLI set keys:
        ({'opts': 'a b'}, {'opts': 'c d'}, 'a b c d (cylc-install)'),
    ]
)
def test_add_cylc_install_to_rose_conf_node_opts(rose_conf, cli_conf, expect):
    rose_node = ConfigNode()
    for key, value in rose_conf.items():
        state = ''
        if key.startswith('!'):
            key = key[1:]
            state = '!'
        rose_node.set([key], value, state=state)
    cli_node = ConfigNode()
    for key, value in cli_conf.items():
        cli_node.set([key], value)

    result = add_cylc_install_to_rose_conf_node_opts(
        rose_node, cli_node)['opts']

    assert result.value == expect

    expect_opt = cli_conf.get('opts', '')
    expect_opt += ' (cylc-install)'

    assert result.comments == [(
        f' Config Options \'{expect_opt}\' from CLI'
        ' appended to options'
        ' already in `rose-suite.conf`.'
    )]
    assert result.state == ''


def test_dump_rose_log(monkeypatch, tmp_path):
    # Pin down the results of the function used to provide a timestamp.
    monkeypatch.setattr(
        DateTimeOperator,
        'process_time_point_str',
        lambda *a, **k: '18151210T0000Z'
    )
    node = ConfigNode()
    node.set(['env', 'FOO'], '"The finger writes."')
    dump_rose_log(tmp_path, node)
    result = (
        tmp_path / 'log/config/18151210T0000Z-rose-suite.conf').read_text()
    assert result == '[env]\nFOO="The finger writes."\n'


@pytest.mark.parametrize(
    'node_, expect, raises',
    [
        pytest.param(
            (
                (['template variables', 'foo'], 'Hello World'),
            ),
            'template variables',
            None,
            id="OK - template variables",
        ),
        pytest.param(
            (
                (['jinja2:suite.rc', 'foo'], 'Hello World'),
            ),
            'jinja2:suite.rc',
            None,
            id="OK - jinja2:suite.rc",
        ),
        pytest.param(
            (
                ('opt', 'a b'),
            ),
            'template variables',
            None,
            id="OK - no template variables section set",
        ),
        pytest.param(
            (
                (['file:stuffin', 'turkey'], 'gobble'),
                (['template variables', 'foo'], 'Hello World'),
            ),
            'template variables',
            None,
            id="OK - No interference with irrelevant sections",
        ),
    ]
)
def test_identify_templating_section(node_, expect, raises):
    node = ConfigNode()
    for item in node_:
        node.set(item[0], item[1])
    if expect is not None:
        assert identify_templating_section(node) == expect
    if raises is not None:
        with pytest.raises(raises):
            identify_templating_section(node)


@pytest.mark.parametrize(
    'input_, expect',
    (
        ([None], 'template variables'),
        (['jinja2'], 'jinja2:suite.rc'),
        (['jinja2:suite.rc'], 'jinja2:suite.rc'),
        ([None, True], '[template variables]'),
        (['jinja2', True], '[jinja2:suite.rc]'),
    )
)
def test_id_templating_section(input_, expect):
    assert id_templating_section(*input_) == expect


@pytest.fixture
def node_with_ROSE_ORIG_HOST():
    def _inner(comment=''):
        tree = ConfigTree()
        node = ConfigNode()
        node.set(['env', 'ROSE_ORIG_HOST'], 'IMPLAUSIBLE_HOST_NAME')
        node['env']['ROSE_ORIG_HOST'].comments = [comment]
        tree.node = node
        process_config(tree, {})
        return node
    yield _inner


@pytest.mark.parametrize('ROSE_ORIG_HOST_overridden', [True, False])
def test_ROSE_ORIG_HOST_replacement_behaviour(
    caplog, node_with_ROSE_ORIG_HOST, ROSE_ORIG_HOST_overridden
):
    """It ignores ROSE_ORIG_HOST set in config.

    Except when the comment ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING has been
    added to ``rose-suite-cylc-install.conf``.
    """
    if ROSE_ORIG_HOST_overridden is True:
        node = node_with_ROSE_ORIG_HOST()
        log_str = (
            '[env]ROSE_ORIG_HOST=IMPLAUSIBLE_HOST_NAME'
            ' will be ignored'
        )
        assert log_str in caplog.records[0].message
        assert node['env']['ROSE_ORIG_HOST'].value != 'IMPLAUSIBLE_HOST_NAME'

    else:
        node = node_with_ROSE_ORIG_HOST(
            ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING)
        assert not caplog.records
        assert node['env']['ROSE_ORIG_HOST'].value == 'IMPLAUSIBLE_HOST_NAME'


@pytest.mark.parametrize(
    'compat_mode, must_include, must_exclude',
    (
        (True, None, 'Use [template variables]'),
        (True, 'root-dir', None),
        (False, 'Use [template variables]', None),
        (False, 'root-dir', None),
    )
)
def test_deprecation_warnings(
    caplog, monkeypatch, compat_mode, must_include, must_exclude
):
    """Method logs warnings correctly.

    Two node items are set:

    * ``jinja2:suite.rc`` should not cause a warning in compatibility mode.
    * ``root-dir=/somewhere`` should always lead to a warning being logged.

    Error messages about
    """
    # Create a node to pass to the method
    # (It's not a tree test because we can use a simpleNamespace in place of
    # a tree object):
    node = ConfigNode()
    node.set(['jinja2:suite.rc'])
    node.set(['root-dir', '~foo'])
    tree = SimpleNamespace(node=node)

    # Patch compatibility mode flag and run the function under test:
    monkeypatch.setattr('cylc.rose.utilities.cylc7_back_compat', compat_mode)
    deprecation_warnings(tree)

    # Check that warnings have/not been logged:
    records = '\n'.join([i.message for i in caplog.records])
    if must_include:
        assert must_include in records
    else:
        assert must_exclude not in records


@pytest.mark.parametrize(
    'tv_string',
    (('template variables'), ('jinja2:suite.rc')),
)
def test_retrieve_installed_cli_opts(tmp_path, tv_string):
    """It merges src, dest and cli.
    """
    # Create a source conifg
    rose_suite_conf = tmp_path / 'src/rose-suite.conf'
    src = rose_suite_conf.parent
    src.mkdir(parents=True)
    rose_suite_conf.touch()
    (src / 'opt').mkdir()
    (src / 'opt/rose-suite-option1.conf').touch()
    (src / 'opt/rose-suite-option2.conf').touch()

    # Create saved CLI from earlier CLI:
    install_conf = tmp_path / 'run/opt/rose-suite-cylc-install.conf'
    install_conf.parent.mkdir(parents=True)
    install_conf.write_text(
        dedent(f'''
        opts = option2
        TOP_LEVEL=false
        [env]
        ENV_LEAVE=true
        ENV_OVERRIDE=false
        [{tv_string}]
        TV_LEAVE=true
        TV_OVERRIDE_D=false
        TV_OVERRIDE_S=false
    ''')
    )

    opts = SimpleNamespace()
    opts.against_source = install_conf.parent.parent
    opts.defines = [
        f'[{tv_string}]TV_OVERRIDE_D=True',
        '[env]ENV_OVERRIDE=true',
        'TOP_LEVEL=true'
    ]
    opts.rose_template_vars = ['TV_OVERRIDE_S=True']
    opts.opt_conf_keys = ['option1']

    opts = retrieve_installed_cli_opts(
        srcdir=src,
        opts=opts,
    )

    assert opts.opt_conf_keys == ['option2', 'option1']

    rose_template_vars = [
        o for o in opts.rose_template_vars if 'ROSE_ORIG_HOST' not in o
    ]
    assert rose_template_vars == [
        'TV_OVERRIDE_S=True',
        'TV_OVERRIDE_D=True',
        'TV_LEAVE=true',
    ]

    defines = [d for d in opts.defines if 'ROSE_ORIG_HOST' not in d]
    assert defines == [
        '[env]ENV_OVERRIDE=true',
        '[env]ENV_LEAVE=true',
        'TOP_LEVEL=true',
    ]


def test_retrieve_installed_cli_opts_returns_unchanged():
    """...if clear_rose_install_opts is true."""
    opts = SimpleNamespace(clear_rose_install_opts=True, against_source=True)
    assert retrieve_installed_cli_opts('Irrelevant', opts) == opts
