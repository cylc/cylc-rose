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
"""Top level module providing entry point functions."""

from pathlib import Path
from typing import Union

from cylc.rose.utilities import (
    copy_config_file,
    dump_rose_log,
    export_environment,
    load_rose_config,
    process_config,
    record_cylc_install_options,
    rose_config_exists,
)


def pre_configure(srcdir=None, opts=None, rundir=None) -> dict:
    """Run before the Cylc configuration is read."""
    if not srcdir:
        # not sure how this could happen
        return {
            # default return value
            'env': {},
            'template_variables': {},
            'templating_detected': None
        }

    # load the Rose config
    config_tree = load_rose_config(Path(srcdir), opts=opts)

    # extract plugin return information from the Rose config
    plugin_result = process_config(config_tree)

    # set environment variables
    export_environment(plugin_result['env'])

    return plugin_result


def post_install(srcdir=None, opts=None, rundir=None) -> Union[dict, bool]:
    """Run after Cylc file installation has completed."""
    from cylc.rose.fileinstall import rose_fileinstall

    if (
        not srcdir
        or not rundir
        or not rose_config_exists(srcdir)
    ):
        # nothing to do here
        return False
    srcdir: Path = Path(srcdir)
    rundir: Path = Path(rundir)

    results = {}
    copy_config_file(srcdir=srcdir, rundir=rundir)
    results['record_install'] = record_cylc_install_options(
        srcdir=srcdir, opts=opts, rundir=rundir
    )
    results['fileinstall'] = rose_fileinstall(rundir, opts)
    # Finally dump a log of the rose-conf in its final state.
    if results['fileinstall']:
        dump_rose_log(rundir=rundir, node=results['fileinstall'])

    return results


def rose_stem():
    """Implements the "rose stem" command."""
    from cylc.rose.stem import get_rose_stem_opts

    parser, opts = get_rose_stem_opts()
    rose_stem(parser, opts)
