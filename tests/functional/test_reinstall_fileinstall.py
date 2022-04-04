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
"""Cylc reinstall is able to use the async fileinstall from rose without
trouble.
"""

import os
import pytest
import shutil
import subprocess

from pathlib import Path
from uuid import uuid4

from cylc.flow.pathutil import get_workflow_run_dir


WORKFLOW_SRC = Path(__file__).parent / '14_reinstall_fileinstall'


@pytest.fixture(scope='module')
def fixture_provide_flow(tmp_path_factory):
    """Provide a cylc workflow based on the contents of a folder which can
    be either validated or installed.
    """
    test_flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'
    srcpath = (tmp_path_factory.getbasetemp() / test_flow_name)
    flowpath = Path(get_workflow_run_dir(test_flow_name))
    shutil.copytree(WORKFLOW_SRC, srcpath)
    (srcpath / 'opt').mkdir(exist_ok=True)
    yield {
        'test_flow_name': test_flow_name,
        'flowpath': flowpath,
        'srcpath': srcpath
    }
    shutil.rmtree(srcpath)
    shutil.rmtree(flowpath)


def test_install_flow(fixture_provide_flow):
    """Run ``cylc install``.
    """
    result = subprocess.run(
        [
            'cylc', 'install',
            '--flow-name', fixture_provide_flow['test_flow_name'],
            '-C', str(fixture_provide_flow['srcpath'])
        ],
        capture_output=True,
        env=os.environ
    )
    assert result.returncode == 0


def test_reinstall_flow(fixture_provide_flow):
    """Run ``cylc reinstall``.
    """
    result = subprocess.run(
        [
            'cylc', 'reinstall',
            fixture_provide_flow['test_flow_name'],
        ],
        capture_output=True,
        env=os.environ
    )
    assert result.returncode == 0
