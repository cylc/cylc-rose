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

from cylc.rose.utilities import (
    copy_config_file,
    dump_rose_log,
    get_rose_vars,
    paths_to_pathlib,
    record_cylc_install_options,
    rose_config_exists,
)


def pre_configure(srcdir=None, opts=None, rundir=None):
    """Run before the Cylc configuration is read."""
    srcdir, rundir = paths_to_pathlib([srcdir, rundir])
    return get_rose_vars(srcdir=srcdir, opts=opts)


def post_install(srcdir=None, opts=None, rundir=None):
    """Run after Cylc file installation has completed."""
    from cylc.rose.fileinstall import rose_fileinstall

    if not rose_config_exists(srcdir, opts):
        return False
    srcdir, rundir = paths_to_pathlib([srcdir, rundir])
    results = {}
    copy_config_file(srcdir=srcdir, rundir=rundir)
    results['record_install'] = record_cylc_install_options(
        srcdir=srcdir, opts=opts, rundir=rundir
    )
    results['fileinstall'] = rose_fileinstall(
        srcdir=srcdir, opts=opts, rundir=rundir
    )
    # Finally dump a log of the rose-conf in its final state.
    if results['fileinstall']:
        dump_rose_log(rundir=rundir, node=results['fileinstall'])

    return results


def rose_stem():
    """Implements the "rose stem" command."""
    from cylc.rose.stem import get_rose_stem_opts

    parser, opts = get_rose_stem_opts()
    rose_stem(parser, opts)
