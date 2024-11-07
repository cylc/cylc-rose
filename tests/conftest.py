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
from functools import partial
import importlib
from io import StringIO
from pathlib import Path
from shlex import split
from shutil import rmtree, copytree
from subprocess import run
import sys
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pytest import UsageError

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

from metomi.rose.resource import ResourceLocator
from metomi.rose.config import ConfigLoader

from cylc.rose.stem import (
    get_rose_stem_opts,
    rose_stem as _rose_stem,
)


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


@pytest.fixture(scope='module')
def monkeymodule():
    """Make monkeypatching available in a module scope."""
    with pytest.MonkeyPatch.context() as mp:
        yield mp


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
    mpatch = pytest.MonkeyPatch()
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


def _cylc_inspection_cli(capsys, caplog, script, gop):
    """Access the CLI for cylc scripts inspecting configurations
    """
    async def _inner(srcpath, args=None, n_args=3):
        parser = gop()
        options = Options(parser, args)()
        output = SimpleNamespace()

        try:
            if n_args == 3:
                await script(parser, options, str(srcpath))
            if n_args == 2:
                # Don't include the parser:
                await script(options, str(srcpath))
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc

        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()

        return output
    return _inner


def _cylc_install_cli(test_dir):
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
        nonlocal test_dir
        if not workflow_name:
            workflow_name = str(
                (test_dir / str(uuid4())[:4]).relative_to(CYLC_RUN_DIR)
            )
        options = Options(
            install_gop(), opts or {}
        )(workflow_name=workflow_name)
        if not options.workflow_name:
            options.workflow_name = workflow_name
        if not opts or not opts.get('no_run_name', ''):
            options.no_run_name = True
        return await cylc_install(options, str(srcpath))
    return _inner


def _cylc_reinstall_cli(test_dir):
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
        nonlocal test_dir
        if not workflow_id:
            workflow_id = str(test_dir.relative_to(CYLC_RUN_DIR))
        options = Options(reinstall_gop(), opts or {})()
        options.skip_interactive = True
        return await cylc_reinstall(options, workflow_id)
    return _inner


@pytest.fixture
def cylc_install_cli(test_dir):
    return _cylc_install_cli(test_dir)


@pytest.fixture(scope='module')
def mod_cylc_install_cli(mod_test_dir):
    return _cylc_install_cli(mod_test_dir)


@pytest.fixture
def cylc_reinstall_cli(test_dir):
    return _cylc_reinstall_cli(test_dir)


@pytest.fixture(scope='module')
def mod_cylc_reinstall_cli(mod_test_dir):
    return _cylc_reinstall_cli(mod_test_dir)


@pytest.fixture
def cylc_validate_cli(capsys, caplog):
    return _cylc_inspection_cli(capsys, caplog, cylc_validate, validate_gop)


@pytest.fixture(scope='module')
def mod_cylc_validate_cli(mod_capsys, mod_caplog):
    return _cylc_inspection_cli(
        mod_capsys, mod_caplog, cylc_validate, validate_gop
    )


@pytest.fixture
async def cylc_inspect_scripts(capsys, caplog):
    """Run all the common Cylc Test scripts likely to call pre-configure.

    * config
    * graph
    * list
    * validate
    * view

    n.b.
    * Function adds arg ``--reference`` to supress image being displayed.
    """

    async def _inner(wid, args):
        results = {}

        # Handle scripts taking a parser or just the output of the parser:
        for script_name, n_args in {
            'config': 3,
            'list': 3,
            'graph': 3,
            'view': 2,
            'validate': 3,
        }.items():

            # Import the script modules:
            script_module = importlib.import_module(
                f'cylc.flow.scripts.{script_name}'
            )

            # Deal with inconsistent API from Cylc:
            if hasattr(script_module, '_main'):
                script = script_module._main
            elif hasattr(script_module, 'run'):
                script = script_module.run
            else:
                raise UsageError(
                    f'Script "{script}\'s" module does not contain a '
                    '"_main" or "run" function'
                )

            # Supress cylc-graph giving a graphical output:
            if script_name == 'graph':
                args['reference'] = True

            results[script_name] = await _cylc_inspection_cli(
                capsys,
                caplog,
                script,
                script_module.get_option_parser,
            )(wid, args, n_args=n_args)

        # Check outputs
        assert all(output.ret == 0 for output in results.values())

        # Return results for more checking if required:
        return results

    return _inner


@pytest.fixture
def rose_stem(test_dir, monkeypatch, request):
    """The Rose Stem command.

    Wraps the "rose_stem" async function for use in tests.

    Cleans up afterwards if the test was successful.
    """
    run_dir = test_dir / str(uuid4())[:4]

    async def _inner(source_dir, cwd=None, **rose_stem_opts):
        nonlocal monkeypatch, request, run_dir

        # point rose-stem at the desired run directory
        rose_stem_opts['no_run_name'] = True
        rose_stem_opts['workflow_name'] = str(
            run_dir.relative_to(CYLC_RUN_DIR)
        )

        # make it look like we're running the "rose stem" CLI
        monkeypatch.setattr('sys.argv', ['stem'])

        # cd into the rose stem project directory (unless overridden)
        monkeypatch.chdir(cwd or source_dir)

        # merge the opts in with the defaults
        parser, opts = get_rose_stem_opts()
        for key, val in rose_stem_opts.items():
            setattr(opts, key, val)

        # run rose stem
        await _rose_stem(parser, opts)

        # return a dictionary of template variables found in the
        # cylc-install optional configuration
        cylc_install_opt_conf = Path(
            run_dir,
            'opt/rose-suite-cylc-install.conf',
        )
        if cylc_install_opt_conf.exists():
            opt_conf = ConfigLoader().load(str(cylc_install_opt_conf))
            return {
                key: node.value  # noqa B035 (false positive)
                for [_, key], node in opt_conf.get(
                    ('template variables',)
                ).walk()
            }
        else:
            return {}

    return _inner


@pytest.fixture()
def mock_global_cfg(monkeypatch):
    """Mock the rose ResourceLocator.default

    Args:
        target: The module to patch.
        conf: A fake rose global config as a string.

    """
    def _inner(target, conf):
        """Get the ResourceLocator.default and patch its get_conf method."""
        obj = ResourceLocator.default()
        monkeypatch.setattr(
            obj, 'get_conf', lambda: ConfigLoader().load(StringIO(conf))
        )

        monkeypatch.setattr(target, lambda *_, **__: obj)

    yield _inner


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


@pytest.fixture
def file_poll():
    """Poll for the existance of a file.
    """
    def _inner(
        fpath: "Path", timeout: int = 5, inverse: bool = False
    ):
        timeout_func(
            lambda: fpath.exists() != inverse,
            f"file {fpath} {'still' if inverse else 'not'} found after "
            f"{timeout} seconds",
            timeout
        )
    return _inner


@pytest.fixture
def purge_workflow(run_ok, file_poll):
    """Ensure workflow is stopped and cleaned"""
    def _inner(id_, timeout=5):
        stop = f'cylc stop {id_} --now --now'
        clean = f'cylc clean {id_}'
        timeout_func(
            partial(run_ok, stop),
            message=f'Not run after {timeout} seconds: {stop}',
            timeout=timeout
        )
        file_poll(
            Path.home() / 'cylc-run' / id_ / '.service/contact',
            inverse=True,
        )
        timeout_func(
            partial(run_ok, clean),
            message=f'Not run after {timeout} seconds: {clean}',
            timeout=timeout
        )
    return _inner


@pytest.fixture
def run_ok():
    """Run a bash script.
    Fail if it fails and return its output.
    """

    def _inner(script: str):
        result = run(split(script), capture_output=True)
        assert (
            result.returncode == 0
        ), f'{script} failed: {result.stderr.decode}'
        return result
    return _inner


def timeout_func(func, message, timeout=5):
    """Wrap a function in a timeout"""
    for _ in range(timeout):
        if func():
            break
        sleep(1)
    else:
        raise TimeoutError(message)


@pytest.fixture
def setup_workflow_source_dir(tmp_path):
    """Copy a workflow from the codebase to a temp-file-path
    and provide that path for use in tests.
    """

    def _inner(code_src):
        nonlocal tmp_path
        # Set up paths for test:
        testpath = tmp_path / 'src'
        testpath.mkdir()

        # the files to install are stored in a directory alongside this
        # test file:
        datapath = Path(__file__).parent / code_src
        if sys.version_info.minor > 7:
            copytree(datapath, testpath, dirs_exist_ok=True)
        else:
            # Python 3.7 bodge:
            import distutils
            distutils.dir_util.copy_tree(str(datapath), str(testpath))

        return datapath, testpath

    yield _inner
