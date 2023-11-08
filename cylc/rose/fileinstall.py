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

"""Utilities related to performing Rose file installation."""

import os
from typing import TYPE_CHECKING, Union

from cylc.rose.utilities import rose_config_exists, rose_config_tree_loader

if TYPE_CHECKING:
    from pathlib import Path
    from cylc.flow.option_parsers import Values
    from metomi.rose.config import ConfigNode


def rose_fileinstall(
    rundir: 'Path',
    opts: 'Values',
) -> 'Union[ConfigNode, bool]':
    """Call Rose Fileinstall."""
    if not rose_config_exists(rundir):
        return False

    # Load the config tree
    config_tree = rose_config_tree_loader(rundir, opts)

    if any(i.startswith('file') for i in config_tree.node.value):
        try:
            startpoint = os.getcwd()
            os.chdir(rundir)
        except FileNotFoundError as exc:
            raise exc
        else:
            # Carry out imports.
            import asyncio

            from metomi.rose.config_processor import ConfigProcessorsManager
            from metomi.rose.fs_util import FileSystemUtil
            from metomi.rose.popen import RosePopener
            from metomi.rose.reporter import Reporter

            # Update config tree with install location
            # NOTE-TO-SELF: value=os.environ["CYLC_WORKFLOW_RUN_DIR"]
            config_tree.node = config_tree.node.set(
                keys=["file-install-root"], value=str(rundir)
            )

            # Artificially set rose to verbose.
            event_handler = Reporter(3)
            fs_util = FileSystemUtil(event_handler)
            popen = RosePopener(event_handler)

            # Get an Asyncio loop if one doesn't exist:
            #   Rose may need an event loop to invoke async interfaces,
            #   doing this here incase we want to go async in cylc-rose.
            # See https://github.com/cylc/cylc-rose/pull/130/files
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

            # Process fileinstall.
            config_pm = ConfigProcessorsManager(event_handler, popen, fs_util)
            config_pm(config_tree, "file")
        finally:
            os.chdir(startpoint)

    return config_tree.node
