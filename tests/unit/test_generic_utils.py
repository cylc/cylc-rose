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
"""Test generic ultilities
"""

import pytest

from pathlib import Path

from cylc.rose.utilities import paths_to_pathlib


@pytest.mark.parametrize(
    'paths, expect',
    [
        # None is passed through:
        ([None, None], [None, None]),
        # Path as string is made Path:
        (['/foot/path/', None], [Path('/foot/path'), None]),
        # Path as Path left alone:
        ([Path('/cycle/path/'), None], [Path('/cycle/path'), None]),
        # Different starting types re-typed independently:
        (
            [Path('/cycle/path/'), '/bridle/path'],
            [Path('/cycle/path'), Path('/bridle/path')]),
    ]
)
def test_paths_to_pathlib(paths, expect):
    assert paths_to_pathlib(paths) == expect
