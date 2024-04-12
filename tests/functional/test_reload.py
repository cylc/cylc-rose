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

import pytest
from subprocess import run

from pathlib import Path

@pytest.fixture
def provide_template_vars_workflow(tmp_path):
    (tmp_path / 'flow.cylc').write_text(
        '#!jinja2\n'
        '[scheduling]\n'
        '    [[graph]]\n'
        '       R1 = foo\n'
        '[runtime]\n'
        '    [[foo]]\n'
        '        script = cylc message -- {{var}}')
    (tmp_path / 'rose-suite.conf').write_text(
        '[template variables]\nvar="rose-suite.conf"')


def test_reinstall_overrides(
    cylc_install_cli, cylc_reinstall_cli, tmp_path, file_poll,
    provide_template_vars_workflow, purge_workflow
):
    """When reinstalling and reloading the new installation are picked up.
    """
    # Install workflow.
    install_results = cylc_install_cli(
        tmp_path, {'rose_template_vars': ['var="CLIinstall"']})
    assert install_results.ret == 0

    # Play workflow
    # TODO: non-subprocess play command:
    play = run(
        [
            'cylc', 'play', '--pause',
            install_results.id,
            '-S', 'var="CLIplay"'
        ],
        capture_output=True
    )
    assert play.returncode == 0

    # Reinstall the workflow:
    reinstall_results = cylc_reinstall_cli(
        install_results.id,
        {'rose_template_vars': ['var="CLIreinstall"']})
    assert reinstall_results.ret == 0

    # Reload the workflow:
    reload_ = run(
        ['cylc', 'reload', install_results.id],
        capture_output=True,
    )
    assert reload_.returncode == 0

    # The config being run has been modified:
    run_dir = Path.home() / 'cylc-run' / install_results.id
    config_log = (run_dir / 'log/config/02-reload-01.cylc')
    file_poll(config_log)

    assert 'cylc message -- CLIreinstall' in config_log.read_text()

    purge_workflow(install_results.id)


def test_restart_overrides(
    cylc_install_cli, cylc_reinstall_cli, tmp_path, file_poll,
    provide_template_vars_workflow, purge_workflow, cylc_stop
):
    """When we restart a workflow, the play CLI options are honoured.

    Example:
        $ cylc install foo -S 'X=0'
        $ cylc play foo -S 'X=1'
        $ cylc stop foo
        $ cylc play foo -S 'X=2'

        Inside the workflow the restart command arg should override the
        content of the files and be X=2.
    """
    # Install workflow.
    install_results = cylc_install_cli(
        tmp_path, {'rose_template_vars': ['var="CLIinstall"']})
    assert install_results.ret == 0

    # Play workflow
    # TODO: non-subprocess play command:
    play = run(
        [
            'cylc', 'play', '--pause',
            install_results.id,
            '-S', 'var="CLIplay"'
        ],
        capture_output=True
    )
    assert play.returncode == 0

    cylc_stop(install_results.id)

    # Play (restart) workflow
    # TODO: non-subprocess play command:
    play = run(
        [
            'cylc', 'play', '--pause',
            install_results.id,
            '-S', 'var="CLIrestart"'
        ],
        capture_output=True
    )
    assert play.returncode == 0

    # The config being run has been modified:
    run_dir = Path.home() / 'cylc-run' / install_results.id
    config_log = (run_dir / 'log/config/02-restart-02.cylc')
    file_poll(config_log)

    assert 'cylc message -- CLIrestart' in config_log.read_text()

    purge_workflow(install_results.id)
