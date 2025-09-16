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

"""Interfaces for Cylc Platforms for use by rose apps."""

from optparse import Values
from pathlib import Path
import sqlite3
import subprocess
import sys
from time import sleep
from typing import (
    Any,
    Dict,
    Tuple,
    Union,
)

from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.id_cli import parse_id
from cylc.flow.pathutil import (
    get_workflow_run_config_log_dir,
    get_workflow_run_dir,
    get_workflow_run_pub_db_path,
)
from cylc.flow.platforms import (
    HOST_REC_COMMAND,
    get_platform,
    is_platform_definition_subshell,
)
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_files import WorkflowFiles


def get_platform_from_task_def(flow: str, task: str) -> Dict[str, Any]:
    """Return the platform dictionary for a particular task.

    Uses the flow definition - designed to be used with tasks
    with unsubmitted jobs. Evaluates platform/host defined as subshell.

    Args:
        flow: The name of the Cylc flow to be queried.
        task: The name of the task to be queried.

    Returns:
        Platform Dictionary.
    """
    workflow_id, _, _ = parse_id(flow, constraint='workflows', src=True)
    flow_file = get_workflow_run_config_log_dir(
        workflow_id,
        WorkflowFiles.FLOW_FILE_PROCESSED,
    )

    config = WorkflowConfig(
        flow,
        flow_file, Values(),
        force_compat_mode=get_compat_mode(get_workflow_run_dir(workflow_id))
    )
    # Get entire task spec to allow Cylc 7 platform from host guessing.
    task_spec = config.pcfg.get(['runtime', task])
    # check for subshell and evaluate
    if (
        task_spec.get('platform')
        and is_platform_definition_subshell(task_spec['platform'])
    ):
        task_spec['platform'] = eval_subshell(task_spec['platform'])
    elif (
        task_spec.get('remote', {}).get('host')
        and HOST_REC_COMMAND.match(task_spec['remote']['host'])
    ):
        task_spec['remote']['host'] = eval_subshell(
            task_spec['remote']['host'])
    platform = get_platform(task_spec)
    return platform


def get_compat_mode(run_dir: Union[str, Path]) -> bool:
    """Check whether this is a Cylc 7 Back compatibility mode workflow:

    See https://github.com/cylc/cylc-rose/issues/319

    Args:
        run_dir: Cylc workflow run directory.
    """
    return (Path(run_dir) / WorkflowFiles.SUITE_RC).exists()


def eval_subshell(platform):
    """Evaluates platforms/hosts defined as subshell"""
    match = HOST_REC_COMMAND.match(platform)
    output = subprocess.run(
        ['bash', '-c', match[2]], capture_output=True, text=True
    )
    return output.stdout.strip()


def get_platforms_from_task_jobs(
    workflow: str, cyclepoint: str
) -> Dict[str, dict]:
    """Get a mapping of task name to platform dict for tasks at the given
    cycle point.

    Uses the workflow database - designed to be used with tasks where jobs
    have been submitted.

    We assume that we want the most recent submission - TODO: why?
    https://github.com/metomi/rose/issues/2924#issuecomment-3292508454

    Args:
        workflow: The name of the Cylc flow to be queried.
        cyclepoint: The CyclePoint at which to query the job.
    """
    parse_id(workflow, constraint='workflows', src=True)
    dao = CylcWorkflowDAO(
        # NOTE: use the public database (only the scheduler thread/process
        # should access the private database)
        get_workflow_run_pub_db_path(workflow),
        is_public=True,
    )
    task_platform_map: Dict[str, Tuple[int, dict]] = {}
    stmt = '''
        SELECT
            name, platform_name, submit_num
        FROM
            task_jobs
        WHERE
            cycle=?
    '''
    db_exc: Exception
    try:
        for _try in range(10):  # connect/execute retries
            try:
                for task, platform_n, submit_num in dao.connect().execute(
                    stmt, [cyclepoint]
                ):
                    try:
                        platform = get_platform(platform_n)
                    except PlatformLookupError as exc:
                        # Skip platforms that cannot be found
                        print(exc, file=sys.stderr)
                        continue
                    if (
                        (
                            task in task_platform_map
                            and task_platform_map[task][0] < submit_num
                        )
                        or task not in task_platform_map
                    ):
                        task_platform_map[task] = (submit_num, platform)
                break
            except sqlite3.OperationalError as exc:
                db_exc = exc
                # sleep between tries to give time for other reads to clear or
                # for the scheduler to copy the private DB over the public one
                # (done in the event of DB locking)
                sleep(0.1)
        else:  # no break
            # we've run out of retries, raise the error from the last retry
            raise db_exc
    finally:
        # NOTE: only tries to close if the connection was successfully
        # opened
        dao.close()

    # get rid of the submit number, we don't want it
    return {
        key: value[1] for key, value in task_platform_map.items()
    }
