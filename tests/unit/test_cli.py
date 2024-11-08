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

"""Tests for CLI Specific functionality"""

import pytest
from types import SimpleNamespace

from cylc.rose.utilities import sanitize_opts


@pytest.mark.parametrize(
    "rose_template_vars, defines, expect_warning",
    (
        (
            ["ROSE_ORIG_HOST=3"],
            [],
            "rose_template_vars:ROSE_ORIG_HOST=3"
            " from command line args will be ignored:",
        ),
        (
            [],
            ["[env]ROSE_ORIG_HOST=3"],
            "defines:[env]ROSE_ORIG_HOST=3"
            " from command line args will be ignored:",
        ),
        (
            ["ROSE_ORIG_HOST=3"],
            ["[env]ROSE_ORIG_HOST=3"],
            [
                "defines:[env]ROSE_ORIG_HOST=3"
                " from command line args will be ignored:",
                "rose_template_vars:ROSE_ORIG_HOST=3"
                " from command line args will be ignored:",
            ],
        ),
        ([], [], False)
    ),
)
def test_sanitzie_opts(caplog, rose_template_vars, defines, expect_warning):
    opts = SimpleNamespace(
        rose_template_vars=rose_template_vars,
        defines=defines,
    )
    sanitize_opts(opts)
    if expect_warning and isinstance(expect_warning, list):
        for warning in expect_warning:
            assert any(warning in w for w in caplog.messages)
    elif expect_warning:
        assert any(expect_warning in w for w in caplog.messages)
    else:
        assert not caplog.messages
