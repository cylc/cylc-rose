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
"""Interfaces for Cylc Platforms for use by rose apps.
"""
from optparse import Values
from pathlib import Path
from typing import Dict, Any

from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_files import parse_reg
from cylc.flow.platforms import get_platform


def get_platform_from_task_def(
    flow: str, task: str
) -> Dict[str, Any]:
    """Return the platform dictionary for a particular task.

    Uses the flow definition - designed to be used with tasks
    with unsubmitted jobs.

    Args:
        flow: The name of the Cylc flow to be queried.
        task: The name of the task to be queried.

    Returns:
        Platform Dictionary.
    """
    _, flow_file = parse_reg(flow, src=True)
    config = WorkflowConfig(flow, flow_file, Values())
    # Get entire task spec to allow Cylc 7 platform from host guessing.
    task_spec = config.pcfg.get(['runtime', task])
    platform = get_platform(task_spec)
    if platform is None:
        raise PlatformLookupError(
            'Platform lookup failed because the platform definition for'
            f' task {task} is {task_spec["platform"]}.'
        )
    return platform


def get_platforms_from_task_jobs(
    flow: str, cyclepoint: str
) -> Dict[str, Any]:
    """Access flow database. Return platform for task at fixed cycle point

    Uses the workflow database - designed to be used with tasks where jobs
    have been submitted. We assume that we want the most recent submission.

    Args:
        flow: The name of the Cylc flow to be queried.
        cyclepoint: The CyclePoint at which to query the job.
        task: The name of the task to be queried.

    Returns:
        Platform Dictionary.
    """
    _, flow_file = parse_reg(flow, src=True)
    dbfilepath = Path(flow_file).parent / '.service/db'
    dao = CylcWorkflowDAO(dbfilepath)
    task_platform_map: Dict = {}
    stmt = (
        'SELECT "name", "platform_name", "submit_num" '
        'FROM task_jobs WHERE cycle=?'
    )
    for row in dao.connect().execute(stmt, [cyclepoint]):
        task, platform_n, submit_num = row
        platform = get_platform(platform_n)
        if (
            (
                task in task_platform_map
                and task_platform_map[task][0] < submit_num
            )
            or task not in task_platform_map
        ):
            task_platform_map[task] = [submit_num, platform]

    # get rid of the submit number, we don't want it
    task_platform_map = {
        key: value[1] for key, value in task_platform_map.items()
    }

    return task_platform_map
