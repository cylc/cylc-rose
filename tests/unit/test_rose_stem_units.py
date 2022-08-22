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
    'args, opts, expect',
    [
        pytest.param(
            [],
            {'stem_sources': ['foo']},
            '',
            id='no-args&sources'
        ),
        pytest.param(
            [],
            None,
            '',
            id='no-args&no-path'
        ),
        pytest.param(
            ['/foo'],
            None,
            None,
            id='args&absolute-path'
        ),
        pytest.param(
            ['foo'],
            None,
            None,
            id='args&relative-path'
        ),
    ]
)
def test_get_source_opt_from_args(tmp_path, monkeypatch, args, opts, expect):
    # Basic setup
    monkeypatch.chdir(tmp_path)
    if opts:
        opts = SimpleNamespace(**opts)
    else:
        opts = SimpleNamespace()
        opts.stem_sources = []

    # Run function
    result = get_source_opt_from_args(opts, args)
    if expect:
        expect = SimpleNamespace(
            source=expect.format(tmp_path=tmp_path),
            stem_sources=[expect.format(tmp_path=tmp_path)]
        )
        assert result == expect
    else:
        assert result == opts
