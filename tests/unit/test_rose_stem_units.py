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
from types import SimpleNamespace

from cylc.rose.stem import get_source_opt_from_args


@pytest.mark.parametrize(
    'args, expect',
    [
        pytest.param(
            [],
            '',
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
            id='absolute-path'
        ),
    ]
)
def test_get_source_opt_from_args(tmp_path, monkeypatch, args, expect):
    # Basic setup
    monkeypatch.chdir(tmp_path)
    opts = SimpleNamespace()

    # Run function
    result = get_source_opt_from_args(opts, args)

    # If an arg is given we are expecting source to be added to the options.
    # Otherwise options should be returned unchanged.
    if expect:
        expect = SimpleNamespace(source=expect.format(tmp_path=tmp_path))
        assert result == expect
    else:
        assert result == opts
