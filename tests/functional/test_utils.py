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

"""Unit tests for utilities."""

from pathlib import Path

from cylc.rose.entry_points import copy_config_file


def test_basic(tmp_path):
    # Create files
    for fname, content in (
        ('src/rose-suite.conf', '[env]\nFOO=2'),
        ('dest/rose-suite.conf', '[env]\nFOO=1'),
    ):
        fname = Path(tmp_path / fname)
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(content)

    # Test
    assert copy_config_file(tmp_path / 'src', tmp_path / 'dest')
    assert Path(tmp_path / 'src/rose-suite.conf').read_text() == (
        Path(tmp_path / 'dest/rose-suite.conf').read_text()
    )
