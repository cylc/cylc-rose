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
"""Functional Test: It ignores commented items in rose-suite.conf

See https://github.com/cylc/cylc-rose/pull/171
"""

from shlex import split
from subprocess import run


def test_cylc_validate(tmp_path):
    """It doesn't pass commented vars to Cylc.
    """
    (tmp_path / 'flow.cylc').write_text("""#!jinja2
{{ assert(UNCOMMENTED is defined, "UNCOMMENTED is not defined") }}
{{ assert(SINGLE is not defined, "SINGLE is defined") }}
{{ assert(DOUBLE is not defined, "DOUBLE is defined") }}
    """)
    (tmp_path / 'rose-suite.conf').write_text(
        '[template variables]\n'
        'UNCOMMENTED="bar"\n'
        '!SINGLE="bar"\n'
        '!!DOUBLE="baz"\n'
    )
    result = run(
        split(f'cylc view --jinja2 {str(tmp_path)}'), capture_output=True)

    if result.returncode == 0:
        assert True
    else:
        raise Exception(result.stderr.decode())
