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
"""Functional tests for top-level function record_cylc_install_options and
"""
from functools import partial
from subprocess import run
from shlex import split
from pathlib import Path
import pytest
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.option_parsers import Options

from cylc.flow.scripts.validate import (
    _main as cylc_validate,
    get_option_parser as validate_gop
)

from cylc.flow.scripts.install import (
    install_cli as cylc_install,
    get_option_parser as install_gop
)

from cylc.flow.scripts.reinstall import (
    reinstall_cli as cylc_reinstall,
    get_option_parser as reinstall_gop
)


def test_workflow_name():
    """Return a UUID to use as a test name"""
    return f'cylc-rose-test-{str(uuid4())[:8]}'


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


def _cylc_validate_cli(capsys, caplog):
    """Access the validate CLI"""
    def _inner(srcpath, args=None):
        parser = validate_gop()
        options = Options(parser, args)()
        output = SimpleNamespace()

        try:
            cylc_validate(parser, options, str(srcpath))
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc

        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()

        return output
    return _inner


def _cylc_install_cli(capsys, caplog):
    """Access the install CLI"""
    def _inner(srcpath, args=None):
        """Install a workflow.

        Args:
            srcpath:
            args: Dictionary of arguments.
        """
        if not args or not args.get('workflow_name', ''):
            id_ = test_workflow_name()
            args = {'workflow_name': id_}

        args.update({'no_run_name': True})
        options = Options(install_gop(), args)()
        output = SimpleNamespace()
        output.id = args['workflow_name']

        try:
            cylc_install(options, str(srcpath))
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc
        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()
        return output
    return _inner


def _cylc_reinstall_cli(capsys, caplog):
    """Access the reinstall CLI"""
    def _inner(workflow_id, opts=None):
        """Install a workflow.

        Args:
            srcpath:
            args: Dictionary of arguments.
        """
        options = Options(reinstall_gop(), opts)()
        output = SimpleNamespace()

        try:
            cylc_reinstall(options, workflow_id)
            output.ret = 0
            output.exc = ''
        except Exception as exc:
            output.ret = 1
            output.exc = exc
        output.logging = '\n'.join([i.message for i in caplog.records])
        output.out, output.err = capsys.readouterr()
        return output
    return _inner


@pytest.fixture
def cylc_install_cli(capsys, caplog):
    return _cylc_install_cli(capsys, caplog)


@pytest.fixture(scope='module')
def mod_cylc_install_cli(mod_capsys, mod_caplog):
    return _cylc_install_cli(mod_capsys, mod_caplog)


@pytest.fixture
def cylc_reinstall_cli(capsys, caplog):
    return _cylc_reinstall_cli(capsys, caplog)


@pytest.fixture(scope='module')
def mod_cylc_reinstall_cli(mod_capsys, mod_caplog):
    return _cylc_reinstall_cli(mod_capsys, mod_caplog)


@pytest.fixture
def cylc_validate_cli(capsys, caplog):
    return _cylc_validate_cli(capsys, caplog)


@pytest.fixture(scope='module')
def mod_cylc_validate_cli(mod_capsys, mod_caplog):
    return _cylc_validate_cli(mod_capsys, mod_caplog)


@pytest.fixture
def file_poll():
    """Poll for the existance of a file.
    """
    def _inner(
        fpath: "Path", timeout: int = 5, inverse: bool = False
    ):
        if inverse:
            def check(f):
                return not f.exists()
        else:
            def check(f):
                return f.exists()

        timeout_func(
            partial(check, fpath),
            f'file {fpath} not found after {timeout} seconds'
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
            message=f'Not run after {timeout} seconds: {stop}')
        file_poll(
            Path.home() / 'cylc-run' / id_ / '.service/contact',
            inverse=True,
        )
        timeout_func(
            partial(run_ok, clean),
            message=f'Not run after {timeout} seconds: {clean}')
    return _inner


@pytest.fixture
def run_ok():
    """Run a bash script.
    Fail if it fails and return its output.
    """
    def _inner(script: str):
        result = run(split(script), capture_output=True)
        assert result.returncode == 0, f'{script} failed: {result.stderr}'
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
