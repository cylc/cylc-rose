# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC SUITE ENGINE.
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
"""Cylc support for reading and interpreting ``rose-suite.conf`` workflow
configuration files.

Top level module providing entry point functions.
"""

import os

from pathlib import Path

from metomi.rose.config import ConfigLoader, ConfigDumper
from cylc.rose.utilities import (
    dump_rose_log,
    get_rose_vars_from_config_node,
    rose_config_exists,
    rose_config_tree_loader,
    merge_rose_cylc_suite_install_conf,
    get_cli_opts_node,
    add_cylc_install_to_rose_conf_node_opts,
)


def get_rose_vars(dir_=None, opts=None):
    """Load template variables from Rose suite configuration.

    This loads the Rose suite configuration tree from the filesystem
    using the shell environment.

    Args:
        dir_(string | pathlib.Path):
            Path to the Rose suite configuration
            (the directory containing the ``rose-suite.conf`` file).
        opts:
            Some sort of options object or string - To be used to allow CLI
            specification of optional configuaration.

    Returns:
        dict - A dictionary of sections of rose-suite.conf.
        For each section either a dictionary or None is returned.
        E.g.
            {
                'env': {'MYVAR': 42},
                'empy:suite.rc': None,
                'jinja2:suite.rc': {
                    'myJinja2Var': {'yes': 'it is a dictionary!'}
                }
            }
    """
    config = {
        'env': {},
        'template_variables': {},
        'templating_detected': None
    }
    # Return a blank config dict if dir_ does not exist
    if not rose_config_exists(dir_, opts):
        return config
    # Load the raw config tree
    config_tree = rose_config_tree_loader(dir_, opts)

    # Extract templatevars from the configuration
    get_rose_vars_from_config_node(
        config,
        config_tree.node,
        os.environ
    )

    # Export environment vars
    for key, val in config['env'].items():
        os.environ[key] = val

    return config


def rose_fileinstall(dir_=None, opts=None, dest_root=None):
    """Call Rose Fileinstall.

    Args:
        dir_(string or pathlib.Path):
            Search for a ``rose-suite.conf`` file in this location.
        dest_root (string or pathlib.Path)

    """
    if dir_ is not None:
        dir_ = Path(dir_)
    if dest_root is not None:
        dest_root = Path(dest_root)

    if not rose_config_exists(dir_, opts):
        return False

    # Load the config tree
    config_tree = rose_config_tree_loader(dir_, opts)

    if any(i.startswith('file') for i in config_tree.node.value):
        try:
            startpoint = os.getcwd()
            os.chdir(dest_root)
        except (FileNotFoundError, TypeError) as exc:
            raise exc
        else:
            # Carry out imports.
            from metomi.rose.config_processor import ConfigProcessorsManager
            from metomi.rose.popen import RosePopener
            from metomi.rose.reporter import Reporter
            from metomi.rose.fs_util import FileSystemUtil

            # Update config tree with install location
            # NOTE-TO-SELF: value=os.environ["CYLC_SUITE_RUN_DIR"]
            config_tree.node = config_tree.node.set(
                keys=["file-install-root"], value=str(dest_root)
            )

            # Artificially set rose to verbose.
            event_handler = Reporter(3)
            fs_util = FileSystemUtil(event_handler)
            popen = RosePopener(event_handler)

            # Process files
            config_pm = ConfigProcessorsManager(event_handler, popen, fs_util)
            config_pm(config_tree, "file")
        finally:
            os.chdir(startpoint)

    dump_rose_log(dest_root=dest_root, node=config_tree.node)

    return True


def record_cylc_install_options(
    dest_root=None,
    opts=None,
    dir_=None,
):
    """Create/modify files recording Cylc install config options.

    Creates a new config based on CLI options and writes it to the workflow
    install location as ``rose-suite-cylc-install.conf``. If
    ``rose-suite-cylc-install.conf`` already exists over-writes changed items,
    except for ``!opts=`` which is merged and simplified.

    If ``!opts=`` have been changed these are appended to those that have
    been written in the installed ``rose-suite.conf``.

    Args:
        _ (pathlib.Path | or str):
            Not used in this function, but requried for consistent entry point.
        opts:
            Cylc option parser object - we want to extract the following
            values:
            - opt_conf_keys (list or str):
                Equivelent of ``rose suite-run --option KEY``
            - defines (list of str):
                Equivelent of ``rose suite-run --define KEY=VAL``
            - suite_defines (list of str):
                Equivelent of ``rose suite-run --define-suite KEY=VAL``
        dest_root (pathlib.Path | or str):
            Path to dump the rose-suite-cylc-conf

    Returns:
        cli_config - Config Node which has been dumped to
        ``rose-suite-cylc-install.conf``.
        rose_suite_conf['opts'] - Opts section of the config node dumped to
        installed ``rose-suite.conf``.
    """
    # Create a config based on command line options:
    cli_config = get_cli_opts_node(opts)
    # Leave now if there is nothing to do:
    if not cli_config:
        return False
    # Construct a path objects representing our target files.
    (Path(dest_root) / 'opt').mkdir(exist_ok=True)
    conf_filepath = Path(dest_root) / 'opt/rose-suite-cylc-install.conf'
    rose_conf_filepath = Path(dest_root) / 'rose-suite.conf'
    dumper = ConfigDumper()
    loader = ConfigLoader()

    # If file exists we need to merge with our new config, over-writing with
    # new items where there are duplicates.

    if conf_filepath.is_file():
        oldconfig = loader.load(str(conf_filepath))
        cli_config = merge_rose_cylc_suite_install_conf(oldconfig, cli_config)

    cli_config.comments = [
        ' This file records CLI Options.'
    ]
    dumper.dump(cli_config, str(conf_filepath))

    # Replace the opts section of the rose-suite.conf in the install location.
    # If we have not a rose-suite.conf but we use one of the Rose-style
    # options we still want to record those options.
    if not rose_conf_filepath.is_file():
        rose_conf_filepath.touch()
    rose_suite_conf = loader.load(str(rose_conf_filepath))
    rose_suite_conf = add_cylc_install_to_rose_conf_node_opts(
        rose_suite_conf, cli_config
    )
    dumper(rose_suite_conf, rose_conf_filepath)
    return cli_config, rose_suite_conf
