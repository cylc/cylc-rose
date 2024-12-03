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

from itertools import product
from pathlib import Path
import shutil
from uuid import uuid4

from cylc.flow.hostuserutil import get_host
from cylc.flow.install import reinstall_workflow
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
    src_flow_name = '10_reinstall_basic'
    workflow_src = Path(__file__).parent / src_flow_name
    test_flow_name = f'cylc-rose-test-{str(uuid4())[:8]}'
    srcpath = (tmp_path_factory.getbasetemp() / test_flow_name)
    flowpath = Path(get_workflow_run_dir(test_flow_name))
    shutil.copytree(workflow_src, srcpath)
    (srcpath / 'opt').mkdir(exist_ok=True)
    for opt in ['a', 'b', 'c', 'd', 'z']:
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
    monkeymodule.setenv('ROSE_SUITE_OPT_CONF_KEYS', 'b')
    name, id_ = await mod_cylc_install_cli(
        fixture_provide_flow['srcpath'],
        fixture_provide_flow['test_flow_name'],
        {
            'opt_conf_keys': ['c'],
        },
    )

    yield {
        'fixture_provide_flow': fixture_provide_flow,
        'name': name,
        'id': id_,
    }


async def test_cylc_validate(fixture_provide_flow, cylc_validate_cli):
    """Sanity check that workflow validates:
    """
    srcpath = fixture_provide_flow['srcpath']
    assert (await cylc_validate_cli(str(srcpath))).ret == 0


@pytest.mark.parametrize(
    'file_, expect',
    [
        (
            'rose-suite.conf', (
                '# Config Options \'b c (cylc-install)\' from CLI appended to'
                ' options already in `rose-suite.conf`.\n'
                'opts=a b c (cylc-install)\n'
            )
        ),
        (
            'opt/rose-suite-cylc-install.conf', (
                '# This file records CLI Options.{version_info}\n'
                '!opts=b c\n'
                f'\n[env]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
                f'\n[template variables]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
            )
        )
    ]
)
def test_cylc_install_files(fixture_install_flow, file_, expect, version_info):
    expect = expect.format(version_info=version_info)
    fpath = fixture_install_flow['fixture_provide_flow']['flowpath']
    assert (fpath / file_).read_text() == expect


@pytest.mark.parametrize(
    'file_, expect',
    [
        (
            'rose-suite.conf', (
                '# Config Options \'b c d (cylc-install)\' from CLI appended '
                'to options already in `rose-suite.conf`.\n'
                'opts=a b c d (cylc-install)\n'
            )
        ),
        (
            'opt/rose-suite-cylc-install.conf', (
                '# This file records CLI Options.{version_info}\n'
                '!opts=b c d\n'
                f'\n[env]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
                f'\n[template variables]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
            )
        )
    ]
)
async def test_cylc_reinstall_files(
    fixture_install_flow,
    monkeymodule,
    mod_cylc_reinstall_cli,
    file_,
    expect,
    version_info,
):
    """Run ``cylc reinstall``.

    By running in a fixture with modular scope we
    can run tests on different aspects of its output as separate tests.
    """
    expect = expect.format(version_info=version_info)
    monkeymodule.delenv('ROSE_SUITE_OPT_CONF_KEYS', raising=False)
    assert await mod_cylc_reinstall_cli(
        fixture_install_flow['id'],
        {'opt_conf_keys': ['d']},
    )
    fpath = fixture_install_flow['fixture_provide_flow']['flowpath']
    assert (fpath / file_).read_text() == expect


@pytest.mark.parametrize(
    'file_, expect',
    [
        (
            'rose-suite.conf', (
                '# Config Options \'b c d (cylc-install)\' from CLI appended '
                'to options already in `rose-suite.conf`.\n'
                'opts=z b c d (cylc-install)\n'
            )
        ),
        (
            'opt/rose-suite-cylc-install.conf', (
                '# This file records CLI Options.{version_info}\n'
                '!opts=b c d\n'
                f'\n[env]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
                f'\n[template variables]\n#{ROHIOS}\nROSE_ORIG_HOST={HOST}\n'
            )
        )
    ]
)
async def test_cylc_reinstall_files2(
    fixture_install_flow,
    monkeymodule,
    mod_cylc_reinstall_cli,
    file_,
    expect,
    version_info,
):
    """Run ``cylc reinstall``.

    This second re-install we change the contents of the source rose-suite.conf
    to check that the reinstall changes the installed workflow based on this
    change.

    By running in a fixture with modular scope we
    can run tests on different aspects of its output as separate tests.

    If a test fails using ``pytest --pdb then``
    ``fixture_install_flow['result'].stderr`` may help with debugging.
    """
    expect = expect.format(version_info=version_info)
    monkeymodule.delenv('ROSE_SUITE_OPT_CONF_KEYS', raising=False)
    (
        fixture_install_flow
        ['fixture_provide_flow']
        ['srcpath']
        / 'rose-suite.conf'
    ).write_text('opts=z\n')
    assert await mod_cylc_reinstall_cli(
        fixture_install_flow['id'],
    )
    fpath = (
        fixture_install_flow
        ['fixture_provide_flow']
        ['flowpath']
    )
    assert (fpath / file_).read_text() == expect


def test_reinstall_workflow(tmp_path):
    """In dry-run mode it checks whether rose-suite.conf has changed.
    """
    # Set up source and run dirs as if installed:
    cylc_install_dir = (
        tmp_path /
        "cylc-run" /
        "flow-name" /
        "_cylc-install")
    cylc_install_dir.mkdir(parents=True)
    source_dir = (tmp_path / "cylc-source" / "flow-name")
    source_dir.mkdir(parents=True)
    (cylc_install_dir / "source").symlink_to(source_dir)
    run_dir = cylc_install_dir.parent

    # Add empty files to both source and run dir:
    for path in product(
        [source_dir, run_dir], ['flow.cylc', 'rose-suite.conf']
    ):
        Path(path[0] / path[1]).touch()

    # Modify the rose-suite.conf
    (source_dir / 'rose-suite.conf').write_text('foo')
    (source_dir / 'flow.cylc').write_text('foo')

    stdout = reinstall_workflow(
        source_dir, "flow-name", run_dir, dry_run=True)

    expect = sorted(['send rose-suite.conf', 'send flow.cylc'])
    assert sorted(stdout.split('\n')) == expect
