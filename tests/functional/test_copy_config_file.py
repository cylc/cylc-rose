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
"""Functional tests for top-level function cylc.rose.entry points
copy_config_file.
"""

from pathlib import Path

import pytest

from cylc.rose.entry_points import copy_config_file


@pytest.mark.parametrize(
    'sources, inputs, expect',
    [
        (
            # Valid sourcedir with rose file, rose file at dest:
            {
                'src/rose-suite.conf': '[env]\nFOO=2',
                'dest/rose-suite.conf': '[env]\nFOO=1'
            },
            {'srcdir': 'src', 'rundir': 'dest'},
            True
        )
    ]
)
def test_basic(tmp_path, sources, inputs, expect):
    # Create files
    for fname, content in sources.items():
        fname = Path(tmp_path / fname)
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(content)

    # Flesh-out filepaths.
    inputs = {
        kwarg: Path(tmp_path / path) for kwarg, path in inputs.items()
        if path is not None
    }

    # Test
    if expect:
        assert copy_config_file(**inputs) == expect
        assert (Path(tmp_path / 'src/rose-suite.conf').read_text() ==
                Path(tmp_path / 'dest/rose-suite.conf').read_text()
                )
    else:
        assert copy_config_file(**inputs) == expect
