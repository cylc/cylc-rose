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

import os
from pathlib import Path
import pytest
from types import SimpleNamespace

from cylc.rose.stem import get_source_opt_from_args


@pytest.mark.parametrize(
    'args, relpath',
    [
        pytest.param(
            ['rose-stem', 'foo'], True,
            id='relative-path'
        ),
        pytest.param(
            ['rose-stem'], True,
            id='no-path'
        ),
        pytest.param(
            ['rose-stem'], False,
            id='absolute-path'
        ),
    ]
)
def test_get_source_opt_from_args(tmp_path, args, relpath):
    os.chdir(tmp_path)
    opts = SimpleNamespace()
    if relpath and len(args) > 1:
        sourcepath = (Path.cwd() / 'foo')
    elif relpath:
        sourcepath = (Path.cwd() / 'rose-stem')
    else:
        sourcepath = (Path.cwd() / 'foo')
        args.append(str(sourcepath))
    expect = SimpleNamespace(source=str(sourcepath))
    sourcepath.mkdir()
    result = get_source_opt_from_args(opts, args)
    assert result == expect
