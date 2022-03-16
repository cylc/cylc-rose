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
"""Tests for platform utils module:
"""

import os
import pytest

from pathlib import Path
from shutil import rmtree
from subprocess import run
from uuid import uuid4
from cylc.flow.exceptions import PlatformLookupError

from cylc.rose.platform_utils import (
    get_platform_from_task_def,
    get_platforms_from_task_jobs
)

from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.parsec.config import ParsecConfig

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
    2. Set up a fake flow database in ``.service/db``.

    Returns:
        flow_name: Name of fake workflow.
        flow_path: Path at which fake workflow is installed.
    """
    # Set up a config
    flow_name: str = f'cylc-rose-platform-utils-test-{str(uuid4())[:6]}'
    flow_path = Path(os.path.expandvars('$HOME/cylc-run')) / flow_name
    flow_path.mkdir(parents=True)
    (flow_path / 'flow.cylc').write_text("""
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
                platform = $(echo "myplatform")
            [[roo]]
                [[[remote]]]
                    host = $(echo "myhost")
            [[BAR]]
                platform = milk
            [[child_of_bar]]
                inherit = BAR
    """)

    # Set up a database
    service_dir = flow_path / '.service'
    service_dir.mkdir(parents=True)
    db_script = (
        b"CREATE TABLE task_jobs("
        b"cycle TEXT, name TEXT, submit_num INTEGER, platform_name TEXT);\n"
        b"INSERT INTO task_jobs (cycle, name, submit_num, platform_name)"
        b"    VALUES ('1', 'bar', 1, 'localhost');\n"
        b"INSERT INTO task_jobs (cycle, name, submit_num, platform_name)"
        b"    VALUES ('1', 'baz', 1, 'dairy');\n"
        b"INSERT INTO task_jobs (cycle, name, submit_num, platform_name)"
        b"    VALUES ('1', 'bar', 2, 'dairy');\n"
        b"INSERT INTO task_jobs (cycle, name, submit_num, platform_name)"
        b"    VALUES ('2', 'baz', 1, 'milk');\n"
    )
    run(
        ['sqlite3', f'{str(service_dir / "db")}'],
        input=db_script
    )

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


def test_get_platform_from_task_def_raises(
    mock_glbl_cfg, fake_flow
):
    """Test getting platform from task definition.

    This is approaching an integration test, because
    although it's only testing one unit of Cylc Rose, that unit
    is calling lots of Cylc Parts, which aren't mocked.
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    with pytest.raises(PlatformLookupError, match='Platform lookup failed.*'):
        get_platform_from_task_def(fake_flow[0], 'kanga')


@pytest.mark.parametrize(
    'task, expected',
    [
        pytest.param('kanga', '$(echo "myplatform")', id='platform subshell'),
        pytest.param('roo', '$(echo "myhost")',  id='remote host subshell'),
    ]
)
def test_get_platform_from_task_def_quiet(
    mock_glbl_cfg, fake_flow, task, expected
):
    """Test getting platform from task definition with platform subshell.
    """
    mock_glbl_cfg(*MOCK_GLBL_CFG)
    actual = get_platform_from_task_def(fake_flow[0], task, quiet=True)
    assert actual == expected


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
