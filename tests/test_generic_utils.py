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
"""Tests utilities which do not manipulate configurations.
"""

import pytest

from pathlib import Path

from cylc.rose.utilities import pathchecker


@pytest.mark.parametrize(
    'path, expect',
    [
        # It returns a path given a str:
        ('/the/garden/path', Path('/the/garden/path')),
        # It returns a path/None unchanged:
        (Path('/the/garden/path'), Path('/the/garden/path')),
        (None, None)
    ]
)
def test_pathchecker_OK(path, expect):
    assert pathchecker(path) == expect


@pytest.mark.parametrize('input', [42, {}, [], b'wurble'])
def test_pathchecker_raises(caplog, input):
    # It raises a TypeError if path is any other type
    with pytest.raises(TypeError, match='Path \'.*\' is a .*. It must be .*'):
        pathchecker(input)
