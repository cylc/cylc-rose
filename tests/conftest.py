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

import asyncio
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.option_parsers import Options
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.scripts.install import get_option_parser as install_gop
from cylc.flow.scripts.install import install_cli as cylc_install
from cylc.flow.scripts.reinstall import get_option_parser as reinstall_gop
from cylc.flow.scripts.reinstall import reinstall_cli as cylc_reinstall
from cylc.flow.scripts.validate import run as cylc_validate
from cylc.flow.scripts.validate import get_option_parser as validate_gop
from cylc.flow.wallclock import get_current_time_string


CYLC_RUN_DIR = Path(get_cylc_run_dir())


@pytest.fixture(scope='module')
def event_loop():
    """This fixture defines the event loop used for each test.

    The default scoping for this fixture is "function" which means that all
    async fixtures must have "function" scoping.

    Defining `event_loop` as a module scoped fixture opens the door to
    module scoped fixtures but means all tests in a module will run in the same
    event loop. This is fine, it's actually an efficiency win but also
    something to be aware of.

    See: https://github.com/pytest-dev/pytest-asyncio/issues/171

    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # gracefully exit async generators
    loop.run_until_complete(loop.shutdown_asyncgens())
    # cancel any tasks still running in this event loop
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.close()


@pytest.fixture()
def workflow_name():
    return 'cylc-rose-test-' + str(uuid4())[:8]


@pytest.fixture(scope='module')
def mod_workflow_name():
    return 'cylc-rose-test-' + str(uuid4())[:8]


@pytest.fixture(scope='module')
def mod_capsys(request):
    from _pytest.capture import SysCapture
    capman = request.config.pluginmanager.getplugin("capturemanager")
    capture_fixture = pytest.CaptureFixture[str](
        SysCapture, request, _ispytest=True)
    capman.set_fixture(capture_fixture)
    capture_fixture._start()
    yield capture_fixture
    capture_fixture.close()
    capman.unset_fixture()


@pytest.fixture(scope='module')
def mod_caplog(request):
    request.node.add_report_section = lambda *args: None
    logging_plugin = request.config.pluginmanager.getplugin('logging-plugin')
    for _ in logging_plugin.pytest_runtest_setup(request.node):
        caplog = pytest.LogCaptureFixture(request.node, _ispytest=True)
    yield caplog
    caplog._finalize()


@pytest.fixture(scope='package', autouse=True)
def set_cylc_version():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch.setenv('CYLC_VERSION', CYLC_VERSION)
    mpatch.undo()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose the result of tests to their fixtures.

    This will add a variable to the "node" object which differs depending on
    the scope of the test.

    scope=function
        `_function_outcome` will be set to the result of the test function.
    scope=module
        `_module_outcome will be set to a list of all test results in
        the module.

    https://github.com/pytest-dev/pytest/issues/230#issuecomment-402580536

    """
    outcome = yield
    rep = outcome.get_result()

    # scope==function
    item._function_outcome = rep

    # scope==module
    _module_outcomes = getattr(item.module, '_module_outcomes', {})
    _module_outcomes[(item.nodeid, rep.when)] = rep
    item.module._module_outcomes = _module_outcomes


def _rm_if_empty(path):
    """Convenience wrapper for removing empty directories."""
    try:
        path.rmdir()
    except OSError:
        return False
    return True


def _pytest_passed(request: pytest.FixtureRequest) -> bool:
    """Returns True if the test(s) a fixture was used in passed."""
    if hasattr(request.node, '_function_outcome'):
        return request.node._function_outcome.outcome in {'passed', 'skipped'}
    return all((
        report.outcome in {'passed', 'skipped'}
        for report in request.node.obj._module_outcomes.values()
    ))


def _cylc_validate_cli(capsys, caplog):
    """Access the validate CLI"""
    async def _inner(srcpath, args=None):
        parser = validate_gop()
        options = Options(parser, args)()
        output = SimpleNamespace()

        try:
            await cylc_validate(parser, options, str(srcpath))
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc

        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()

        return output
    return _inner


def _cylc_install_cli(capsys, caplog, test_dir):
    """Access the install CLI"""
    async def _inner(srcpath, workflow_name=None, opts=None):
        """Install a workflow.

        Args:
            srcpath:
                The workflow to install
            workflow_name:
                The workflow ID prefix to install this workflow as.

                If you leave this blank, it will use the module/function's
                test directory as appropriate.
            opts:
                Dictionary of arguments for cylc install.

        """
        nonlocal capsys, caplog, test_dir
        if not workflow_name:
            workflow_name = str(
                (test_dir / str(uuid4())[:4]).relative_to(CYLC_RUN_DIR)
            )
        options = Options(
            install_gop(), opts or {}
        )(workflow_name=workflow_name)
        output = SimpleNamespace()
        if not options.workflow_name:
            options.workflow_name = workflow_name
        if not opts or not opts.get('no_run_name', ''):
            options.no_run_name = True

        try:
            output.name, output.id = await cylc_install(options, str(srcpath))
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc
        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()
        return output
    return _inner


def _cylc_reinstall_cli(capsys, caplog, test_dir):
    """Access the reinstall CLI"""
    async def _inner(workflow_id=None, opts=None):
        """Install a workflow.

        Args:
            workflow_id:
                The workflow ID to reinstall.

                If you leave this blank, it will use the module/function's
                test directory as appropriate.
            args:
                Dictionary of arguments for cylc reinstall.

        """
        nonlocal capsys, caplog, test_dir
        if not workflow_id:
            workflow_id = str(test_dir.relative_to(CYLC_RUN_DIR))
        options = Options(reinstall_gop(), opts or {})()
        output = SimpleNamespace()

        try:
            await cylc_reinstall(options, workflow_id)
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            # raise
            output.ret = 1
            output.exc = exc
        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()
        return output
    return _inner


@pytest.fixture
def cylc_install_cli(capsys, caplog, test_dir):
    return _cylc_install_cli(capsys, caplog, test_dir)


@pytest.fixture(scope='module')
def mod_cylc_install_cli(mod_capsys, mod_caplog):
    return _cylc_install_cli(mod_capsys, mod_caplog, mod_test_dir)


@pytest.fixture
def cylc_reinstall_cli(capsys, caplog, test_dir):
    return _cylc_reinstall_cli(capsys, caplog, test_dir)


@pytest.fixture(scope='module')
def mod_cylc_reinstall_cli(mod_capsys, mod_caplog, mod_test_dir):
    return _cylc_reinstall_cli(mod_capsys, mod_caplog, mod_test_dir)


@pytest.fixture
def cylc_validate_cli(capsys, caplog):
    return _cylc_validate_cli(capsys, caplog)


@pytest.fixture(scope='module')
def mod_cylc_validate_cli(mod_capsys, mod_caplog):
    return _cylc_validate_cli(mod_capsys, mod_caplog)


@pytest.fixture(scope='session')
def run_dir():
    """The cylc run directory for this host."""
    CYLC_RUN_DIR.mkdir(exist_ok=True)
    yield CYLC_RUN_DIR


@pytest.fixture(scope='session')
def ses_test_dir(request, run_dir):
    """The root run dir for test flows in this test session."""
    timestamp = get_current_time_string(use_basic_format=True)
    uuid = f'cylc-rose-test-{timestamp}-{str(uuid4())[:4]}'
    path = Path(run_dir, uuid)
    path.mkdir(exist_ok=True)
    yield path
    _rm_if_empty(path)


@pytest.fixture(scope='module')
def mod_test_dir(request, ses_test_dir):
    """The root run dir for test flows in this test module."""
    path = Path(ses_test_dir, request.module.__name__)
    path.mkdir(exist_ok=True)
    yield path
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=False)
    else:
        # test failed -> remove the test dir if empty
        _rm_if_empty(path)


@pytest.fixture
def test_dir(request, mod_test_dir):
    """The root run dir for test flows in this test function."""
    path = Path(mod_test_dir, request.function.__name__)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=False)
    else:
        # test failed -> remove the test dir if empty
        _rm_if_empty(path)
