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

import pytest
import shutil
import shlex
import subprocess

from pathlib import Path
from uuid import uuid4

from cylc.flow.pathutil import get_workflow_run_dir


@pytest.fixture(scope='module')
def fixture_provide_flow(tmp_path_factory):
    # Set up paths for test:
    srcpath = tmp_path_factory.getbasetemp() / 'src'
    datapath = Path(__file__).parent / 'fileinstall_data'
    for path in [srcpath]:
        path.mkdir()

    # Create a unique flow name for this test:
    flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'

    # Create source suite:
    (srcpath / 'flow.cylc').write_text(
        '[scheduling]\n'
        '    initial cycle point = 2020\n'
        '    [[graph]]\n'
        '        R1 = pointless\n'
        '[runtime]\n'
        '    [[pointless]]\n'
        '        script = true\n'
    )
    (srcpath / 'rose-suite.conf').touch()
    (srcpath / 'opt').mkdir()
    (srcpath / 'opt/rose-suite-A.conf').touch()
    (srcpath / 'opt/rose-suite-B.conf').touch()
    yield srcpath, datapath, flow_name


@pytest.fixture(scope='module')
def fixture_install_flow(fixture_provide_flow):
    srcpath, datapath, flow_name = fixture_provide_flow
    cmd = shlex.split(
        f'cylc install --flow-name {flow_name} -C {str(srcpath)} '
        '--no-run-name '  # Avoid having to keep looking a sub-dir.
        '--opt-conf-key="A" -O "B" '
        '--define "[env]FOO=42" -D "[jinja2:suite.rc]BAR=84" '
        '--rose-template-variable="FLAKE=99" -S "CORNETTO=120" '
    )
    result = subprocess.run(cmd, capture_output=True)
    destpath = Path(get_workflow_run_dir(flow_name))

    yield srcpath, datapath, flow_name, result, destpath

    shutil.rmtree(destpath)


def test_rose_fileinstall_validate(fixture_provide_flow):
    """Workflow validates:
    """
    srcpath, _, _ = fixture_provide_flow
    assert subprocess.run(['cylc', 'validate', str(srcpath)]).returncode == 0


def test_rose_fileinstall_run(fixture_install_flow):
    """Workflow installs:
    """
    _, _, _, result, _ = fixture_install_flow
    assert result.returncode == 0


def test_rose_fileinstall_rose_conf(fixture_install_flow):
    _, _, _, result, destpath = fixture_install_flow
    assert (destpath / 'rose-suite.conf').read_text() == (
        "# Config Options 'A B (cylc-install)' from CLI appended to options "
        "already in `rose-suite.conf`.\n"
        "opts=A B (cylc-install)\n"
    )


def test_rose_fileinstall_rose_suite_cylc_install_conf(fixture_install_flow):
    _, _, _, result, destpath = fixture_install_flow
    assert (destpath / 'opt/rose-suite-cylc-install.conf').read_text() == (
        "# This file records CLI Options.\n\n"
        "!opts=A B\n\n"
        "[env]\n"
        "FOO=42\n\n"
        "[jinja2:suite.rc]\n"
        "BAR=84\n"
        "CORNETTO=120\n"
        "FLAKE=99\n"
    )
