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

"""Functional tests for Rose file installation."""

from pathlib import Path
import shutil
from uuid import uuid4

from cylc.flow.pathutil import get_workflow_run_dir
import pytest


@pytest.fixture
def fixture_provide_flow(tmp_path):
    # Set up paths for test:
    srcpath = tmp_path / 'src'
    datapath = Path(__file__).parent / 'fileinstall_data'
    for path in [srcpath]:
        path.mkdir()

    # Create a unique flow name for this test:
    flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'

    # Create source workflow:
    (srcpath / 'flow.cylc').write_text(
        '[scheduling]\n'
        '    initial cycle point = 2020\n'
        '    [[dependencies]]\n'
        '        [[[R1]]]\n'
        '            graph = pointless\n'
        '[runtime]\n'
        '    [[pointless]]\n'
        '        script = true\n'
    )
    (srcpath / 'rose-suite.conf').write_text(
        '[file:lib/python/lion.py]\n'
        f'source={str(datapath)}/lion.py\n'
        '[file:data]\n'
        f'source={str(datapath)}/*.data\n'
    )
    yield srcpath, datapath, flow_name


@pytest.fixture
def fixture_install_flow(fixture_provide_flow, request, cylc_install_cli):
    srcpath, datapath, flow_name = fixture_provide_flow
    result = cylc_install_cli(str(srcpath), {'workflow_name': flow_name})
    destpath = Path(get_workflow_run_dir(flow_name))

    yield srcpath, datapath, flow_name, result, destpath
    if not request.session.testsfailed:
        shutil.rmtree(destpath, ignore_errors=True)


def test_rose_fileinstall_validate(fixture_provide_flow, cylc_validate_cli):
    """Workflow validates:
    """
    srcpath, _, _ = fixture_provide_flow
    assert cylc_validate_cli(str(srcpath)).ret == 0


def test_rose_fileinstall_run(fixture_install_flow):
    """Workflow installs:
    """
    _, _, _, result, _ = fixture_install_flow
    assert result.ret == 0


def test_rose_fileinstall_subfolders(fixture_install_flow):
    """File installed into a sub directory:
    """
    _, datapath, _, _, destpath = fixture_install_flow
    assert ((destpath / 'lib/python/lion.py').read_text() ==
            (datapath / 'lion.py').read_text())


def test_rose_fileinstall_concatenation(fixture_install_flow):
    """Multiple files concatenated on install(source contained wildcard):
    """
    _, datapath, _, _, destpath = fixture_install_flow
    assert ((destpath / 'data').read_text() ==
            ((datapath / 'randoms1.data').read_text() +
            (datapath / 'randoms3.data').read_text()
             ))
