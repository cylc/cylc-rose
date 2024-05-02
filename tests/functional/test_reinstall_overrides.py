
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
"""Functional tests checking Cylc reinstall and reload behaviour is correct
WRT to deletion of Rose Options at the end of the post install plugin.
https://github.com/cylc/cylc-rose/pull/312
"""


from pathlib import Path
from textwrap import dedent


async def test_reinstall_overrides(
    cylc_install_cli,
    cylc_reinstall_cli,
    workflow_name,
    file_poll,
    tmp_path,
    purge_workflow,
    run_ok
):
    """When reinstalling and reloading the new installation are picked up.
    > cylc install this -S 'var=CLIinstall'
    > cylc play this --pause
    > cylc reinstall this -S 'var=CLIreinstall'
    > cylc play this --pause
    See https://github.com/cylc/cylc-flow/issues/5968
    """
    (tmp_path / 'flow.cylc').write_text(dedent("""        #!jinja2
        [scheduling]
            [[graph]]
               R1 = foo
        [runtime]
            [[foo]]
                script = cylc message -- {{var}}
        """))
    (tmp_path / 'rose-suite.conf').write_text(
        '[template variables]\nvar="rose-suite.conf"')

    # Install workflow.
    wid, _ = await cylc_install_cli(
        tmp_path,
        workflow_name=workflow_name,
        opts={'rose_template_vars': ['var="CLIinstall"']})

    # Play workflow
    run_ok(f'cylc play --pause {wid}')

    # Reinstall the workflow:
    await cylc_reinstall_cli(
        wid,
        {'rose_template_vars': ['var="CLIreinstall"']})

    # Reload the workflow:
    run_ok(f'cylc reload {wid}')

    # The config being run has been modified:
    run_dir = Path.home() / 'cylc-run' / wid
    config_log = (run_dir / 'log/config/02-reload-01.cylc')
    file_poll(config_log)
    assert 'cylc message -- CLIreinstall' in config_log.read_text()

    purge_workflow(wid)