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
from textwrap import dedent

import pytest

from cylc.flow.pathutil import get_workflow_run_dir


# @pytest.fixture(scope='module')
@pytest.fixture
def workflow_source_dir(tmp_path):
    """A source dir with a Rose config that configures file installation."""
    # Set up paths for test:
    srcpath = tmp_path / 'src'
    srcpath.mkdir()

    # the files to install are stored in a directory alongside this test file
    datapath = Path(__file__).parent / 'fileinstall_data'

    # Create a unique flow name for this test:
    # Create source workflow:
    (srcpath / 'flow.cylc').touch()
    (srcpath / 'rose-suite.conf').write_text(dedent(f'''
        [file:lib/python/lion.py]
        source={datapath}/lion.py

        [file:data]
        source={datapath}/*.data
    '''))
    yield srcpath, datapath


@pytest.fixture
async def installed_workflow(
    workflow_source_dir,
    cylc_install_cli,
):
    srcpath, datapath = workflow_source_dir
    result = await cylc_install_cli(srcpath)
    assert result.ret == 0  # ensure the workflow installed successfully
    workflow_id = result.id
    run_dir = Path(get_workflow_run_dir(workflow_id))
    yield datapath, workflow_id, result, run_dir


async def test_rose_fileinstall_subfolders(installed_workflow):
    """It should perform file installation creating directories as needed."""
    datapath, _, _, destpath = installed_workflow
    assert (destpath / 'lib/python/lion.py').read_text() == (
        (datapath / 'lion.py').read_text()
    )


def test_rose_fileinstall_concatenation(installed_workflow):
    """It should install multiple sources into a single file.

    Note source contains wildcard.
    """
    datapath, _, _, destpath = installed_workflow
    assert (destpath / 'data').read_text() == (
        (datapath / 'randoms1.data').read_text()
        + (datapath / 'randoms3.data').read_text()
    )


async def test_rose_fileinstall_error(tmp_path, cylc_install_cli):
    """It should capture fileinstallation errors."""
    (tmp_path / 'flow.cylc').touch()
    (tmp_path / 'rose-suite.conf').write_text(dedent('''
        [file:bad]
        source=no-such-file
    '''))

    result = await cylc_install_cli(tmp_path)
    assert (
        'file:bad=source=no-such-file: bad or missing value'
    ) in str(result.exc)
