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
Cylc Rose is the bridge between Rose suite configurations and Cylc workflows.

Cylc Rose is a replacement for the ``rose suite-run`` command (present in Rose
versions 2019.01 and earlier). It reads the ``rose-suite.conf`` file and
performs the required actions.

Rose Stem
#########

Cylc Rose provides a Rose Stem command, if FCM is installed on your system.
See `the Rose Stem documentation <https://metomi.github.io/rose/2019.01.2/html/tutorial/rose/furthertopics/rose-stem.html>`_
"""
