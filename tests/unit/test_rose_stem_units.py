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
"""Functional tests for top-level function record_cylc_install_options and
"""

import pytest
from pytest import param
from types import SimpleNamespace

from cylc.rose.stem import (
    get_source_opt_from_args, StemRunner, SUITE_RC_PREFIX)

from metomi.rose.reporter import Reporter
from metomi.rose.popen import RosePopener
from metomi.rose.fs_util import FileSystemUtil


@pytest.mark.parametrize(
    'args, expect',
    [
        pytest.param(
            [],
            None,
            id='no-path'
        ),
        pytest.param(
            ['/foo'],
            '/foo',
            id='absolute-path'
        ),
        pytest.param(
            ['foo'],
            '{tmp_path}/foo',
            id='relative-path'
        ),
    ]
)
def test_get_source_opt_from_args(tmp_path, monkeypatch, args, expect):
    """It converts Rose 2 CLI features to options usable by Rose Stem
    """
    monkeypatch.chdir(tmp_path)
    opts = SimpleNamespace()

    result = get_source_opt_from_args(opts, args).source

    if expect is None:
        assert result == expect
    else:
        assert result == expect.format(tmp_path=str(tmp_path))


@pytest.fixture
def get_StemRunner():
    def _inner(kwargs, options=None):
        if options is None:
            options = {}
        """Create a StemRunner objects with some options set."""
        opts = SimpleNamespace(**{'verbosity': 1, 'quietness': 1})
        for k, v in options.items():
            setattr(opts, k, v)
        stemrunner = StemRunner(opts, **kwargs)
        return stemrunner
    return _inner


@pytest.mark.parametrize(
    'attribute, object_, kwargs', [
        param('reporter', Reporter, {}, id='reporter default'),
        param('reporter', str, {'reporter': 'foo'}, id='reporter set'),
        param('popen', RosePopener, {}, id='popen default'),
        param('popen', str, {'popen': 'foo'}, id='popen set'),
        param('fs_util', FileSystemUtil, {}, id='fs_util default'),
        param('fs_util', str, {'fs_util': 'foo'}, id='fs_util set')
    ]
)
def test_StemRunner_init(get_StemRunner, attribute, object_, kwargs):
    """It handles __init__ with different kwargs."""
    stemrunner = get_StemRunner(kwargs)
    item = getattr(stemrunner, attribute)
    if isinstance(object_, str):
        assert item == kwargs[attribute]
    else:
        assert isinstance(item, object_)


@pytest.mark.parametrize(
    'exisiting_defines',
    [
        param([], id='no existing defines'),
        param(['opts=(cylc-install)'], id='existing defines')
    ]
)
def test__add_define_option(get_StemRunner, capsys, exisiting_defines):
    """It adds to defines, rather than replacing any."""
    stemrunner = get_StemRunner(
        {'reporter': print}, {'defines': exisiting_defines})
    assert stemrunner._add_define_option('FOO', '"bar"') is None
    assert f'{SUITE_RC_PREFIX}FOO="bar"' in stemrunner.opts.defines
    assert 'Variable FOO set to "bar"' in capsys.readouterr().out
