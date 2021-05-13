# Copyright (C) British Crown (Met Office) & Contributors.
#
# This file is part of Rose, a framework for meteorological suites.
#
# Rose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Rose. If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------
"""
Tests for cylc.rose.stem
========================

Structure
---------

#. ``setup_stem_repo`` is a module scoped fixture which creates a Rose-Stem
   repository which is used for all the tests.
#. ``rose_stem_run_template`` is a class scoped fixture, which runs a rose
   stem command. Most of the tests are encapsulated in classes to allow
   this expensive fixture to be run only once per class. Most of the tests
   check that the rose-stem has returned 0, and then check that variables
   have been written to a job file.
#. For each test class there is a fixture encapsulating the test to be run.

.. code::

    ┌───────┬──────────┬───────────┬───────────┬───────────────┐
    │       │          │           │           │Test rose-stem │
    │       │ test     │ rose-stem │ Class     │returned 0     │
    │set-up │ specific │ runner    │ container ├───────────────┤
    │repo   │ fixture  │ fixture   │           │Test for output│
    │fixture│ (set up  │           │ Only run  │strings "foo"  │
    │       │ rose-stem│ (run      │ class     ├───────────────┤
    │       │ command) │ rose-stem)│ fixture   │Test for output│
    │       │          │           │ once      │strings "bar"  │
    │       ├──────────┼─ ── ── ── ├───────────┼───────────────┤
    │       │          │           │           │               │
    │       │          │           │           ├───────────────┤
    │       │          │           │           │               │
    │       │          │           │           ├───────────────┤
    │       │          │           │           │               │

Debugging
---------
Because of the tasks being run in subprocesses debugging can be a little
tricky. As a result there is a commented ``breakpoint`` in
``rose_stem_run_template`` indicating a location where it might be useful
to investigate failing tests.


"""

import os
import pytest
import re
import shutil
import subprocess

from pathlib import Path
from uuid import uuid4

from cylc.flow.hostuserutil import get_host
from cylc.flow.pathutil import get_workflow_run_dir


HOST = get_host()


@pytest.fixture(scope='module')
def monkeymodule():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope='module')
def fixture_provide_flow(tmp_path_factory):
    """Provide a cylc workflow based on the contents of a folder which can
    be either validated or installed.
    """
    src_flow_name = '13_ROSE_ORIG_HOST'
    workflow_src = Path(__file__).parent / src_flow_name
    test_flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'
    srcpath = (tmp_path_factory.getbasetemp() / test_flow_name)
    flowpath = Path(get_workflow_run_dir(test_flow_name))
    shutil.copytree(workflow_src, srcpath)
    yield {
        'test_flow_name': test_flow_name,
        'flowpath': flowpath,
        'srcpath': srcpath
    }
    shutil.rmtree(srcpath)
    shutil.rmtree(flowpath)


@pytest.fixture(scope='module')
def fixture_install_flow(fixture_provide_flow, monkeymodule):
    """Run ``cylc install``.

    By running in a fixture with modular scope we
    can run tests on different aspects of its output as separate tests.

    If a test fails then using ``pytest --pdb`` and
    ``fixture_install_flow['result'].stderr`` may help with debugging.
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
    install_conf_path = (
        fixture_provide_flow['flowpath'] /
        'runN/opt/rose-suite-cylc-install.conf'
    )
    text = install_conf_path.read_text()
    text = re.sub('ROSE_ORIG_HOST=.*', 'ROSE_ORIG_HOST=foo', text)
    install_conf_path.write_text(text)
    yield {
        **fixture_provide_flow,
        'result': result
    }


@pytest.fixture(scope='module')
def fixture_play_flow(fixture_install_flow):
    """Run cylc flow in a fixture.
    """
    flowname = fixture_install_flow['test_flow_name']
    flowname = f"{flowname}/runN"
    play = subprocess.run(
        ['cylc', 'play', flowname, '--no-detach'],
        capture_output=True, text=True
    )
    return play


def test_cylc_validate_srcdir(fixture_install_flow):
    """Sanity check that workflow validates:
    """
    srcpath = fixture_install_flow['srcpath']
    validate = subprocess.run(
        ['cylc', 'validate', str(srcpath)], capture_output=True
    )
    search = re.findall(
        r'WARNING - ROSE_ORIG_HOST \(.*\) is: (.*)', validate.stderr.decode()
    )
    assert validate.returncode == 0
    assert search == [HOST, HOST]


def test_cylc_validate_rundir(fixture_install_flow):
    """Sanity check that workflow validates:
    """
    flowpath = fixture_install_flow['flowpath'] / 'runN'
    validate = subprocess.run(
        ['cylc', 'validate', str(flowpath)], capture_output=True
    )
    search = re.findall(
        r'WARNING - ROSE_ORIG_HOST \(.*\) is: (.*)', validate.stderr.decode()
    )
    assert validate.returncode == 0
    assert search == ['foo', 'foo']


def test_cylc_install_run(fixture_install_flow):
    """install flow works."""
    assert fixture_install_flow['result'].returncode == 0
