# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC SUITE ENGINE.
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

from pathlib import Path
import subprocess
import pytest
import os


def envar_exporter(dict_):
    for key, val in dict_.items():
        os.environ[key] = val


@pytest.mark.parametrize(
    'srcdir, expect',
    [
        (
            '07_cli_override',
            (
                b'Jinja2Error: Jinja2 Assertion Error: failed 1.1\nContext '
                b'lines:\n\n# 1. This should fail unless cylc validate --set '
                b'CLI_VAR=42\n{{ assert(CLI_VAR=="Wobble", "failed 1.1") }}\t'
                b'<-- Exception\n'
            ),
        ),
        (
            '08_template_engine_conflict',
            (
                b'FileParseError: Plugins set templating engine = empy which '
                b'does not match #!jinja2 set in flow.cylc.\n'
            )
        )
    ]
)
def test_validate_fail(srcdir, expect):
    srcdir = Path(__file__).parent / srcdir
    sub = subprocess.run(
        ['cylc', 'validate', str(srcdir)], capture_output=True
    )
    assert sub.returncode != 0
    if expect:
        assert sub.stderr == expect


@pytest.mark.parametrize(
    'srcdir, envvars, args',
    [
        ('00_jinja2_basic', None, None),
        ('01_empy', None, None),
        ('02_env', None, None),
        (
            '04_opts_set_from_env',
            {'ROSE_SUITE_OPT_CONF_KEYS': 'Gaelige'},
            None
        ),
        (
            '05_opts_set_from_rose_suite_conf',
            {'ROSE_SUITE_OPT_CONF_KEYS': ''},
            None
        ),
        ('06_jinja2_thorough', {'XYZ': 'xyz'}, None),
        ('07_cli_override', {'XYZ': ''}, ["--set=CLI_VAR='Wobble'"]),
    ],
)
def test_validate(tmp_path, srcdir, envvars, args):
    if envvars is not None:
        envvars = os.environ.update(envvars)
    srcdir = Path(__file__).parent / srcdir
    script = ['cylc', 'validate', str(srcdir)]
    if args:
        script = script + args
    assert (
        subprocess.run(script, env=envvars)
    ).returncode == 0


@pytest.mark.parametrize(
    'srcdir, envvars, args',
    [
        ('00_jinja2_basic', None, None),
        ('01_empy', None, None),
        (
            '04_opts_set_from_env',
            {'ROSE_SUITE_OPT_CONF_KEYS': 'Gaelige'},
            None
        ),
        (
            '05_opts_set_from_rose_suite_conf',
            {'ROSE_SUITE_OPT_CONF_KEYS': ''},
            None
        ),
        ('06_jinja2_thorough', {'XYZ': 'xyz'}, None),
    ],
)
def test_process(tmp_path, srcdir, envvars, args):
    if envvars is not None:
        envvars = os.environ.update(envvars)
    srcdir = Path(__file__).parent / srcdir
    result = subprocess.run(
        ['cylc', 'view', '-p', '--stdout', str(srcdir)],
        capture_output=True,
        env=envvars
    ).stdout.decode()
    expect = (srcdir / 'processed.conf.control').read_text()
    assert expect == result
