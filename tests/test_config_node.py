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

import pytest

from metomi.isodatetime.datetimeoper import DateTimeOperator
from metomi.rose.config import (
    ConfigNode,
)
from metomi.rose.config_processor import ConfigProcessError

from cylc.rose.utilities import (
    get_rose_vars_from_config_node,
    add_cylc_install_to_rose_conf_node_opts,
    dump_rose_log,
    identify_templating_section,
    MultipleTemplatingEnginesError
)


def test_blank():
    """It should provide only standard vars for a blank config."""
    ret = {}
    node = ConfigNode()
    get_rose_vars_from_config_node(ret, node, {})
    assert set(ret.keys()) == {
        'template_variables', 'templating_detected', 'env'
    }
    assert set(ret['env'].keys()) == {
        'ROSE_ORIG_HOST',
        'ROSE_SITE',
        'ROSE_VERSION',
    }


def test_invalid_templatevar():
    """It should wrap eval errors as something more informative."""
    ret = {}
    node = ConfigNode()
    node.set(['jinja2:suite.rc', 'X'], 'Y')
    with pytest.raises(ConfigProcessError):
        get_rose_vars_from_config_node(ret, node, {})


def test_get_rose_vars_from_config_node__unbound_env_var(caplog):
    """It should fail if variable unset in environment.
    """
    ret = {}
    node = ConfigNode()
    node.set(['env', 'X'], '${MYVAR}')
    with pytest.raises(ConfigProcessError) as exc:
        get_rose_vars_from_config_node(ret, node, {})
    assert exc.match('env=X: MYVAR: unbound variable')


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

    expect_opt = ''
    if 'opts' in cli_conf:
        expect_opt = cli_conf['opts']
    expect_opt += ' (cylc-install)'

    assert result.comments == [(
        f' Config Options \'{expect_opt}\' from CLI '
        'appended to options '
        'already in `rose-suite.conf`.'
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
    result = (tmp_path / 'log/conf/18151210T0000Z-rose-suite.conf').read_text()
    assert '[env]\nFOO="The finger writes."\n' == result


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
                (['empy:suite.rc', 'foo'], 'Hello World'),
            ),
            'empy:suite.rc',
            None,
            id="OK - empy:suite.rc",
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
                (['empy:suite.rc', 'foo'], 'Hello World'),
                (['jinja2:suite.rc', 'foo'], 'Hello World'),
            ),
            None,
            MultipleTemplatingEnginesError,
            id="FAILS - clashing template sections set",
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
