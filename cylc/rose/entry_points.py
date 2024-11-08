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

import os
from pathlib import Path
from typing import TYPE_CHECKING

from cylc.rose.utilities import (
    ROSE_SUITE_OPT_CONF_KEYS,
    copy_config_file,
    dump_rose_log,
    export_environment,
    load_rose_config,
    process_config,
    record_cylc_install_options,
    retrieve_installed_cli_opts,
    rose_config_exists,
    sanitize_opts,
)

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Values


def pre_configure(srcdir: Path, opts: 'Values') -> dict:
    """Run before the Cylc configuration is read."""
    if not rose_config_exists(srcdir):
        # nothing to do here
        return {}

    opts = sanitize_opts(opts)

    # If we are validating against source, load saved CLI options
    # from previous install, as saved in the rose-suite-cylc-install.conf
    if (
        getattr(opts, 'against_source', False)
        and isinstance(opts.against_source, Path)
    ):
        opts = retrieve_installed_cli_opts(srcdir, opts)

    # load the source Rose config
    config_tree = load_rose_config(Path(srcdir), opts=opts)

    # extract plugin return information from the Rose config
    plugin_result = process_config(config_tree)

    # set environment variables
    export_environment(plugin_result['env'])

    return plugin_result


def post_install(srcdir: Path, rundir: str, opts: 'Values') -> bool:
    """Run after Cylc file installation has completed."""
    from cylc.rose.fileinstall import rose_fileinstall

    if not rose_config_exists(srcdir):
        # nothing to do here
        return False

    _rundir: Path = Path(rundir)

    # transfer the rose-suite.conf file
    copy_config_file(srcdir=srcdir, rundir=_rundir)

    # write cylc-install CLI options to an optional config
    record_cylc_install_options(srcdir, _rundir, opts)

    # perform file installation
    config_node = rose_fileinstall(_rundir, opts)
    if config_node:
        dump_rose_log(rundir=_rundir, node=config_node)

    # Having dumped the config we clear rose options
    # as they do not apply after this.
    # see https://github.com/cylc/cylc-rose/pull/312
    opts.rose_template_vars = []
    opts.opt_conf_keys = []
    opts.defines = []
    os.unsetenv(ROSE_SUITE_OPT_CONF_KEYS)

    return True


def rose_stem():
    """Implements the "rose stem" command."""
    import asyncio
    from cylc.rose.stem import get_rose_stem_opts, rose_stem

    parser, opts = get_rose_stem_opts()
    asyncio.run(
        rose_stem(parser, opts)
    )
