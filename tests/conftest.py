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

from cylc.flow import __version__ as CYLC_VERSION


@pytest.fixture(scope='package', autouse=True)
def set_cylc_version():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch.setenv('CYLC_VERSION', CYLC_VERSION)
    mpatch.undo()
