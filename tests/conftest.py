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

import pytest
from types import SimpleNamespace

from cylc.flow import __version__ as CYLC_VERSION

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

from cylc.flow.scripts.view import (
    _main as cylc_view,
    get_option_parser as view_gop
)


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


def _cylc_cli(capsys, caplog, script, gop, parser_reqd=False):
    """Access the CLI for a cylc script:

    Args:
        capsys, caplog: Pytest fixtures - use `mod_cap~` to make
            the fixture calling this function module scoped.
        script: Script CLI to run
        gop: get_option parser for a given script.
        parser_reqd: Many scripts don't require the parser object,
            just an id/path and the options object. If the parser
            object is required, set True.

    Returns: An object which looks a bit like the result
        of running:

        subprocess.run(
            ['cylc', 'script']
            + [f"--{opt}: value" for opt, value in opts.items()]
        )
    """
    def _inner(srcpath, opts=None):
        parser = gop()
        options = parser.get_default_values()
        options.__dict__.update({
            'templatevars': [], 'templatevars_file': []
        })

        if opts is not None:
            options.__dict__.update(opts)

        output = SimpleNamespace()

        try:
            if parser_reqd:
                script(parser, options, str(srcpath))
            else:
                script(options, str(srcpath))
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
    return _cylc_cli(
        capsys, caplog,
        cylc_install, install_gop
    )


@pytest.fixture(scope='module')
def mod_cylc_install_cli(mod_capsys, mod_caplog):
    return _cylc_cli(
        mod_capsys, mod_caplog,
        cylc_install, install_gop
    )


@pytest.fixture
def cylc_reinstall_cli(capsys, caplog):
    return _cylc_cli(
        capsys, caplog,
        cylc_reinstall, reinstall_gop
    )


@pytest.fixture(scope='module')
def mod_cylc_reinstall_cli(mod_capsys, mod_caplog):
    return _cylc_cli(
        mod_capsys, mod_caplog,
        cylc_reinstall, reinstall_gop
    )


@pytest.fixture
def cylc_validate_cli(capsys, caplog):
    return _cylc_cli(
        capsys, caplog,
        cylc_validate, validate_gop, parser_reqd=True
    )


@pytest.fixture(scope='module')
def mod_cylc_validate_cli(mod_capsys, mod_caplog):
    return _cylc_cli(
        mod_capsys, mod_caplog,
        cylc_validate, validate_gop, parser_reqd=True
    )


@pytest.fixture
def cylc_view_cli(capsys, caplog):
    return _cylc_cli(capsys, caplog, cylc_view, view_gop)
