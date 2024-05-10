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

"""Tests for platform utils module."""

import os
from pathlib import Path
from shutil import rmtree
import sqlite3
from uuid import uuid4

from cylc.rose.platform_utils import (
    force_compat_mode,
    get_platform_from_task_def,
    get_platforms_from_task_jobs,
)

from cylc.flow import __version__ as cylc_version
from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.pathutil import get_workflow_run_pub_db_path
from cylc.flow.workflow_db_mgr import CylcWorkflowDAO
import pytest


MOCK_GLBL_CFG = (
    'cylc.flow.platforms.glbl_cfg',
    '''
    [platforms]
        [[localhost]]
            hosts = localhost
        [[milk]]
            hosts = milk
        [[dairy]]
            hosts = cheese, eggs
        [[my-platform]]
            hosts = ham, mushrooms
        [[my-host]]
            hosts = tomato, flour
    ''')


@pytest.fixture
def mock_glbl_cfg(tmp_path, monkeypatch):
    """A Pytest fixture for fiddling global config values.

    * Hacks the specified `glbl_cfg` object.
    * Can be called multiple times within a test function.

    Args:
        pypath (str):
            The python-like path to the global configuation object you want
            to fiddle.
            E.G. if you want to hack the `glbl_cfg` in
            `cylc.flow.scheduler` you would provide
            `cylc.flow.scheduler.glbl_cfg`
        global_config (str):
            The globlal configuration as a multi-line string.

    Example:
        Change the value of `UTC mode` in the global config as seen from
        `the scheduler` module.

        def test_something(mock_glbl_cfg):
            mock_glbl_cfg(
                'cylc.flow.scheduler.glbl_cfg',
                '''
                    [scheduler]
                        UTC mode = True
                '''
            )

    """
    # TODO: modify Parsec so we can use StringIO rather than a temp file.
    def _mock(pypath, global_config):
        nonlocal tmp_path, monkeypatch
        global_config_path = tmp_path / 'global.cylc'
        global_config_path.write_text(global_config)
        glbl_cfg = ParsecConfig(SPEC)
        glbl_cfg.loadcfg(global_config_path)

        def _inner(cached=False):
            nonlocal glbl_cfg
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    yield _mock
    rmtree(tmp_path)


@pytest.fixture(scope='session')
def fake_flow():
    """Set up enough of an installed flow for tests in module.

    1. Set up an installed ``flow.cylc`` config file.
    2. Set up a fake flow database in ``log/db``.

    Returns:
        flow_name: Name of fake workflow.
        flow_path: Path at which fake workflow is installed.
    """
    # Set up a config
    flow_name: str = f'cylc-rose-platform-utils-test-{str(uuid4())[:6]}'
    flow_path = Path(os.path.expandvars('$HOME/cylc-run')) / flow_name
    flow_path.mkdir(parents=True)
    flow_cylc = flow_path / 'flow.cylc'
    flow_cylc.write_text("""
        [scheduling]
            [[graph]]
                R1 = foo & bar & baz & qux & child_of_bar
        [runtime]
            [[foo]]
                platform = dairy
            [[bar]]
                platform = milk
            [[baz]]
                # platform unset, should default to localhost.
            [[qux]]
                [[[remote]]]
                    host = cheese
            [[kanga]]
                platform = $(echo "my-platform")
            [[roo]]
                [[[remote]]]
                    host = $(echo "my-host")
            [[BAR]]
                platform = milk
            [[child_of_bar]]
                inherit = BAR
    """)
    flow_processed = flow_path / 'log/config/flow-processed.cylc'
    flow_processed.parent.mkdir(exist_ok=True, parents=True)
    flow_processed.symlink_to(flow_path / 'flow.cylc')

    # Set up a database
    db_file = get_workflow_run_pub_db_path(flow_name)
    with CylcWorkflowDAO(db_file, create_tables=True) as dao:
        conn = dao.connect()
        conn.execute(
            r"INSERT INTO task_jobs (cycle, name, submit_num, platform_name)"
            r"    VALUES"
            r"        ('1', 'bar', 1, 'localhost'),"
            r"        ('1', 'baz', 1, 'dairy'),"
            r"        ('1', 'bar', 2, 'dairy'),"
            r"        ('2', 'baz', 1, 'milk')"
        )
        conn.execute(
            r"INSERT INTO workflow_params"
            f"    VALUES ('cylc_version', {cylc_version!r});",
        )
        conn.commit()
        conn.close()

    yield flow_name, flow_path

    # Clean up after ourselves:
    rmtree(flow_path)


@pytest.mark.parametrize(
    'task_name, expected_platform_n',
    [
        pytest.param('foo', 'dairy', id='platform from task'),
        pytest.param('baz', 'localhost', id='task platform unset'),
        pytest.param('qux', 'dairy', id='Cylc 7 (host) task def'),
        pytest.param('child_of_bar', 'milk', id='task inherits platform')
    ]
)
def test_get_platform_from_task_def(
    mock_glbl_cfg, fake_flow, task_name, expected_platform_n
):
    """Test getting platform from task definition.

    This is approaching an integration test, because
    although it's only testing one unit of Cylc Rose, that unit
    is calling lots of Cylc Parts, which aren't mocked.
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    platform = get_platform_from_task_def(fake_flow[0], task_name)
    assert platform['name'] == expected_platform_n


@pytest.mark.parametrize(
    'task, expected',
    [
        pytest.param('kanga', "my-platform", id='platform subshell'),
        pytest.param('roo', "my-host", id='remote host subshell'),
    ]
)
def test_get_platform_from_task_def_subshell(
    mock_glbl_cfg, fake_flow, task, expected
):
    """Test getting platform from task definition with platform subshell.
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    platform = get_platform_from_task_def(fake_flow[0], task)
    assert platform['name'] == expected


@pytest.mark.parametrize(
    'create, expect',
    (
        (['suite.rc', 'log/conf/flow-processed.cylc'], True),
        (['suite.rc', 'foo/bar/any-old.file'], True),
        (['flow.cylc', 'log/conf/flow-processed.cylc'], False),
        (['flow.cylc', 'where/flow-processed.cylc'], False),
    )
)
def test_force_compat_mode(tmp_path, create, expect):
    """It checks whether there is a suite.rc two directories up."""
    for file in create:
        file = tmp_path / file
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    assert force_compat_mode(file) == expect


@pytest.mark.parametrize(
    'task, cycle, expect',
    [
        pytest.param('bar', '1', 'dairy', id='ensure most recent submit used'),
        pytest.param('baz', '1', 'dairy', id='basic test'),
        pytest.param('baz', '2', 'milk', id='pick a diffn\'t cycle point')
    ]
)
def test_get_platforms_from_task_jobs(
    mock_glbl_cfg, fake_flow, task, cycle, expect
):
    """Test getting platform info for a task from the workflow database.
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    flow_name, flow_path = fake_flow
    task_platforms_map = get_platforms_from_task_jobs(flow_name, cycle)
    assert task_platforms_map[task]['name'] == expect


def test_get_platforms_db_retry(
    mock_glbl_cfg, fake_flow, monkeypatch
):
    """It should retry if a DB connection/operation fails.

    The public DB can get "locked" as a result of something trying to read from
    it whilst the scheduler is trying to write to it.

    In the event of error we should wait a little and retry the read. The
    scheduler will overwrite the public DB to resolve the lock given enough
    time.

    See https://github.com/cylc/cylc-rose/pull/155
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    flow_name, flow_path = fake_flow
    task, cycle, expect = ('bar', '1', 'dairy')

    # make the workflow connection raise an error
    def opp_err(*args, **kwargs):
        raise sqlite3.OperationalError

    monkeypatch.setattr(
        'cylc.rose.platform_utils.CylcWorkflowDAO.connect',
        opp_err,
    )

    # get_platforms_from_task_jobs should fail after exhausting its retries
    # because it cannot connect to the database
    with pytest.raises(sqlite3.OperationalError):
        get_platforms_from_task_jobs(flow_name, cycle)

    # now we'll allow the second retry to succeed by undoing the patch
    # (time.sleep is called between retries)
    def undo():
        monkeypatch.undo()
        mock_glbl_cfg(*MOCK_GLBL_CFG)

    monkeypatch.setattr(
        'cylc.rose.platform_utils.sleep',
        undo(),
    )

    # the first attempt will fail, however, the second attempt should succeed
    task_platforms_map = get_platforms_from_task_jobs(flow_name, cycle)
    assert task_platforms_map[task]['name'] == expect
