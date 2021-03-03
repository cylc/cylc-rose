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
"""

Cylc Rose
=========

Cylc Rose is the bridge between Rose suite configurations and Cylc workflows.

Cylc Rose is a replacement for the ``rose suite-run`` command (present in Rose
versions 2019.01 and earlier). It reads the ``rose-suite.conf`` file and
performs the required actions.

Pre install
===========

Before running ``cylc install`` or ``cylc reinstall``  Cylc Rose will:

- Load any rose configuration defined in the installation source directory.
- Export any environment variables set in the ``[env]`` section
  of the configuration.
- Return the configuration so that Cylc can access template variables.

Post install
============

After running ``cylc install`` or ``cylc reinstall`` Cylc Rose will:

- Copy a ``rose-suite.conf`` file if it is in the source directory.
- Create a ``rose-suite-cylc-install.conf`` file saving options set by the
  user on the command line.  Cylc Rose will save this file in the
  ``rundir/opt/`` directory.
- If a ``rose-suite-cylc-install.conf`` already exists in ``rundir/opt/``
  Cylc Rose will merge the new and old options. Cylc Rose gives new options
  higher priority.
- If you run ``cylc reinstall --clear-rose-install-options``, Cylc Rose will
  delete any previous ``rose-suite-cylc-install.conf`` file.
- Create a ``rose-suite.conf``` in the run directory. In this file Cylc Rose
  will add ``(cylc-install)`` to the end of the ``opts`` setting.
- Install any files described by ``[file:<filename>]`` sections in the Rose
  configuration.
- Record the final configuration used for this install. Cylc Rose writes
  the record to ``log/conf/<timestamp>-rose-suite.conf``.

.. Insert links to documentation for install and reinstall.
.. Insert links to glossary for source directory and run directory.

"""
