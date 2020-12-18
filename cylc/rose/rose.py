# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""

import os
import shlex

from ast import literal_eval
from pathlib import Path

# from cylc.flow import LOG
from metomi.rose.config_processor import ConfigProcessError
from metomi.rose.env import env_var_process, UnboundEnvironmentVariableError
from metomi.rose import __version__ as ROSE_VERSION
from metomi.rose.resource import ResourceLocator
from cylc.flow.hostuserutil import get_host


class MultipleTemplatingEnginesError(Exception):
    ...


def get_rose_vars(dir_=None, opts=None):
    """Load Jinja2 Vars from rose-suite.conf in dir_

    Args:
        dir_(string or Pathlib.path object):
            Search for a ``rose-suite.conf`` file in this location.
        opts:
            Some sort of options object or string - To be used to allow CLI
            specification of optional configuaration.

    Returns:
        A dictionary of sections of rose-suite.conf.
        For each section either a dictionary or None is returned.
        E.g.
            {
                'env': {'MYVAR': 42},
                'empy:suite.rc': None,
                'jinja2:suite.rc': {
                    'myJinja2Var': {'yes': 'it is a dictionary!'}
                }
            }

    TODO:
        - Consider allowing ``[jinja2:flow.conf]`` as an alias for
          consistency with cylc.
    """
    config = {
        'env': {},
        'template_variables': {},
        'templating_detected': None
    }
    # Return a blank config dict if dir_ does not exist
    if not rose_config_exists(dir_):
        return config

    # Load the raw config tree
    config_tree = rose_config_tree_loader(dir_, opts)

    templating = None
    if (
        'jinja2:suite.rc' in config_tree.node.value and
        'empy:suite.rc' in config_tree.node.value
    ):
        raise MultipleTemplatingEnginesError(
            "You should not define both jinja2 and empy in the same "
            "configuration file."
        )
    elif 'jinja2:suite.rc' in config_tree.node.value:
        templating = 'jinja2'
    elif 'empy:suite.rc' in config_tree.node.value:
        templating = 'empy'
    if templating:
        config['templating_detected'] = templating

    # Get Values for standard ROSE variables.
    rose_orig_host = get_host()
    rose_site = ResourceLocator().get_conf().get_value(['site'], '')

    # Create env section if it doesn't already exist.
    if 'env' not in config_tree.node.value:
        config_tree.node.set(['env'])

    # For each section add standard variables and process variables.
    for section in ['env', f'{templating}:suite.rc']:
        if section not in config_tree.node.value:
            continue

        # Add standard ROSE_VARIABLES
        config_tree.node[section].set(['ROSE_SITE'], rose_site)
        config_tree.node[section].set(['ROSE_VERSION'], ROSE_VERSION)
        config_tree.node[section].set(['ROSE_ORIG_HOST'], rose_orig_host)

        # Use env_var_process to process variables which may need expanding.
        for key, node in config_tree.node.value[section].value.items():
            try:
                config_tree.node.value[
                    section
                ].value[key].value = env_var_process(node.value)
                if section == 'env':
                    os.environ[key] = node.value
            except UnboundEnvironmentVariableError as exc:
                raise ConfigProcessError(['env', key], node.value, exc)

    # For each of the template language sections extract items to a simple
    # dict to be returned.
    if 'env' in config_tree.node.value:
        config['env'] = {
            item[0][1]: item[1].value for item in
            config_tree.node.value['env'].walk()
        }

    if f"{templating}:suite.rc" in config_tree.node.value:
        config['template_variables'] = {
            item[0][1]: item[1].value for item in
            config_tree.node.value[f"{templating}:suite.rc"].walk()
        }
    # Add the entire config to ROSE_SUITE_VARIABLES to allow for programatic
    # access.
    if templating is not None:
        for key, value in config['template_variables'].items():
            # The special variables are already Python variables.
            if key not in ['ROSE_ORIG_HOST', 'ROSE_VERSION', 'ROSE_SITE']:
                config['template_variables'][key] = literal_eval(value)

    # Add ROSE_SUITE_VARIABLES to config of templating engines in use.
    if templating is not None:
        config['template_variables'][
            'ROSE_SUITE_VARIABLES'] = config['template_variables']

    # Add environment vars to the environment.
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
    if not rose_config_exists(dir_):
        return False

    # Load the config tree
    config_tree = rose_config_tree_loader(dir_, opts)

    if any(['file' in i for i in config_tree.node.value]):

        # Carry out imports.
        from metomi.rose.config_processor import ConfigProcessorsManager
        from metomi.rose.popen import RosePopener
        from metomi.rose.reporter import Reporter
        from metomi.rose.fs_util import FileSystemUtil

        # Update config tree with install location
        # NOTE-TO-SELF: value=os.environ["CYLC_SUITE_RUN_DIR"]
        config_tree.node = config_tree.node.set(
            keys=["file-install-root"], value=dest_root
        )

        # Artificially set rose to verbose.
        # TODO - either use Cylc Log as event handler, or get Cylc Verbosity
        # settings to pass to Rose Reporter.
        event_handler = Reporter(3)
        fs_util = FileSystemUtil(event_handler)
        popen = RosePopener(event_handler)

        # Process files
        config_pm = ConfigProcessorsManager(event_handler, popen, fs_util)
        config_pm(config_tree, "file")

    return True


def rose_config_exists(dir_):
    """Does a directory contain a rose-suite config?

    Args:
        dir_(str or pathlib.Path object):
            location to test.

    Returns:

    """
    if dir_ is None:
        return False

    # Return None if rose-suite.conf do not exist.
    if isinstance(dir_, str):
        dir_ = Path(dir_)
    top_level_file = dir_ / 'rose-suite.conf'
    if not top_level_file.is_file():
        return False

    return True


def rose_config_tree_loader(dir_=None, opts=None):
    """Get a rose config tree from a given dir

    Args:
        dir_(string or Pathlib.path object):
            Search for a ``rose-suite.conf`` file in this location.
        opts:
            Some sort of options object or string - To be used to allow CLI
            specification of optional configuaration.
    Returns:
        A Rose ConfigTree object.
    """
    from metomi.rose.config_tree import ConfigTreeLoader

    opt_conf_keys = []
    # get optional config key set as environment variable:
    opt_conf_keys_env = os.getenv("ROSE_SUITE_OPT_CONF_KEYS")
    if opt_conf_keys_env:
        opt_conf_keys += shlex.split(opt_conf_keys_env)
    # ... or as command line options
    if 'opt_conf_keys' in dir(opts) and opts.opt_conf_keys:
        opt_conf_keys += opts.opt_conf_keys

    # Optional definitions
    redefinitions = []
    if 'defines' in dir(opts) and opts.defines:
        redefinitions = opts.defines

    # Load the actual config tree
    config_tree = ConfigTreeLoader().load(
        str(dir_),
        'rose-suite.conf',
        opt_keys=opt_conf_keys,
        defines=redefinitions
    )

    return config_tree
