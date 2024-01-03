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

"""Functional tests for reinstalling of config files.
This test does the following:

1. Validates a workflow.
2. Installs a workflow with some opts set using -O and
   ROSE_SUITE_OPT_CONF_KEYS.
3. Re-install workflow.
4. After modifying the source ``rose-suite.conf``, re-install the flow again.

At each step it checks the contents of
- ~/cylc-run/temporary-id/rose-suite.conf
- ~/cylc-run/temporary-id/opt/rose-suite-cylc-install.conf
"""

from pathlib import Path
import shutil
from uuid import uuid4

from cylc.flow.hostuserutil import get_host
from cylc.flow.pathutil import get_workflow_run_dir
import pytest

from cylc.rose.utilities import (
    ROSE_ORIG_HOST_INSTALLED_OVERRIDE_STRING as ROHIOS,
)

HOST = get_host()


@pytest.fixture(scope='module')
def monkeymodule():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope='module')
def fixture_provide_flow(tmp_path_factory, request):
    """Provide a cylc workflow based on the contents of a folder which can
    be either validated or installed.
    """
    src_flow_name = '11_reinstall_clean'
    workflow_src = Path(__file__).parent / src_flow_name
    test_flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'
    srcpath = (tmp_path_factory.getbasetemp() / test_flow_name)
    flowpath = Path(get_workflow_run_dir(test_flow_name))
    shutil.copytree(workflow_src, srcpath)
    (srcpath / 'opt').mkdir(exist_ok=True)
    for opt in ['foo', 'bar', 'baz']:
        (srcpath / f'opt/rose-suite-{opt}.conf').touch()
    yield {
        'test_flow_name': test_flow_name,
        'flowpath': flowpath,
        'srcpath': srcpath
    }
    if not request.session.testsfailed:
        shutil.rmtree(srcpath)
        shutil.rmtree(flowpath)


@pytest.fixture(scope='module')
async def fixture_install_flow(
    fixture_provide_flow, monkeymodule, mod_cylc_install_cli
):
    """Run ``cylc install``.

    By running in a fixture with modular scope we
    can run tests on different aspects of its output as separate tests.

    If a test fails using ``pytest --pdb then``
    ``fixture_install_flow['result'].stderr`` may help with debugging.
    """
    result = await mod_cylc_install_cli(
        fixture_provide_flow['srcpath'],
        fixture_provide_flow['test_flow_name'],
        {
            'opt_conf_keys': ['bar'],
            'defines': ['[env]FOO=1']
        }
    )
    yield {
        'fixture_provide_flow': fixture_provide_flow,
        'result': result
    }


def test_cylc_install_run(fixture_install_flow):
    assert fixture_install_flow['result'].ret == 0


@pytest.mark.parametrize(
    'file_, expect',
    [
        (
            'opt/rose-suite-cylc-install.conf', (
                '# This file records CLI Options.\n\n'
                '!opts=bar\n\n'
                '[env]\n'
                f'FOO=1\n#{ROHIOS}\n'
                f'ROSE_ORIG_HOST={HOST}\n'
                f'\n[template variables]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
            )
        ),
    ]
)
def test_cylc_install_files(fixture_install_flow, file_, expect):
    fpath = fixture_install_flow['fixture_provide_flow']['flowpath']
    assert (fpath / file_).read_text() == expect


@pytest.fixture(scope='module')
async def fixture_reinstall_flow(
    fixture_install_flow, monkeymodule, mod_cylc_reinstall_cli
):
    """Run ``cylc reinstall --clear-rose-install-options``.

    Ensure that a reinstalled workflow ignores existing
    rose-suite-cylc-install.conf if asked to do so.

    By running in a fixture with modular scope we
    can run tests on different aspects of its output as separate tests.

    If a test fails using ``pytest --pdb then``
    ``fixture_install_flow['result'].stderr`` may help with debugging.
    """
    monkeymodule.delenv('ROSE_SUITE_OPT_CONF_KEYS', raising=False)
    result = await mod_cylc_reinstall_cli(
        (
            fixture_install_flow['fixture_provide_flow']['test_flow_name']
        ),
        {
            'opt_conf_keys': ['baz'],
            'defines': ['[env]BAR=2'],
            'clear_rose_install_opts': True
        }
    )
    yield {
        'fixture_install_flow': fixture_install_flow,
        'result': result
    }


def test_cylc_reinstall_run(fixture_reinstall_flow):
    assert fixture_reinstall_flow['result'].ret == 0


@pytest.mark.parametrize(
    'file_, expect',
    [
        (
            'opt/rose-suite-cylc-install.conf', (
                '# This file records CLI Options.\n\n'
                '!opts=baz\n\n'
                '[env]\n'
                f'BAR=2\n#{ROHIOS}\n'
                f'ROSE_ORIG_HOST={HOST}\n'
                f'\n[template variables]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
            )
        )
    ]
)
def test_cylc_reinstall_files(fixture_reinstall_flow, file_, expect):
    fpath = (
        fixture_reinstall_flow
        ['fixture_install_flow']
        ['fixture_provide_flow']
        ['flowpath']
    )
    assert (fpath / file_).read_text() == expect
