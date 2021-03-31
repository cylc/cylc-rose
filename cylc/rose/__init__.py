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

Rose Config
-----------

A fuller description of
:rose:ref:`rose suite config is available here<Rose Suites>`.

Cylc-rose allows you to set environment and template variables in a
configuration file called ``rose-suite.conf``. The following sections are
permitted in the ``rose-suite.conf`` files:

.. csv-table::
   :header: config item, description

   ``opts=A B C``, A space limited list of optional configs.
   ``[env]``, "Variables which the cylc-rose plugin will export to the
   environment."
   ``[template variables]``, "Variables which can be used by Jinja2 or Empy
   in the workflow definition."
   ``[file:destination]``, A file from one or more sources to be installed.

.. note::

   For compatibility with Cylc 7 sections ``[suite.rc:empy]`` and
   ``[suite.rc:jinja2]`` will be processed, but are deprecated and provided
   for ease of porting Cylc 7 workflows.


Additional CLI options
----------------------
You can use command line options to set or override
any setting you could put in a ``rose-suite.conf`` file: If you
have Cylc Rose installed see ``cylc install --help``.


Cylc Install Optional Config
----------------------------

If Cylc-Rose is installed, using ``cylc install`` with a Rose Suite will
write a record of command line options set in
``$CYLC_RUN_DIR/workflow_name/opt/rose-suite-cylc-install.conf``.


Example
-------

For a suite with the following definitions in the :term:`source directory`:

rose-suite.conf

.. code-block:: ini

   [template variables]
   NAME='Mars'


flow.cylc

.. code-block:: cylc

   #!jinja2
   [scheduling]
       initial cycle point = 2020
       [[graph]]
           R1 = Hello_{{ NAME }}

   [runtime]
       [[Hello_{{ NAME }}]]
           script = True

If you then ran

.. code-block:: bash

   cylc install


Your final workflow would have the variable ``NAME`` inserted:

.. code-block:: diff

   - Before processing
   + After processing

   -           R1 = Hello_{{ NAME }}
   +           R1 = Hello_Mars

   -       [[Hello_{{ NAME }}]]
   +       [[Hello_Mars]]


Rose Stem
=========

Cylc Rose provides a Rose Stem command, if FCM is installed on your system.
See `the Rose Stem documentation
<https://metomi.github.io/rose/2019.01.2/html/tutorial/rose/furthertopics/rose-stem.html>`_

"""

__version__ = '0.1.1'
