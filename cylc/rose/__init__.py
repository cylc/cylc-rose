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
"""
Cylc Rose
=========

Cylc Rose is the bridge between Rose suite configurations and Cylc workflows.

Cylc Rose allows ``cylc install`` to replace the ``rose suite-run``
command (present in Rose versions 2019.01 and earlier). It reads the
``rose-suite.conf`` file and:

- Makes environment and template variables available
  to Cylc.
- Installs files.
- Records information in about the configuration installed in
  ``~/cylc-run/<workflow>/opt/rose-suite-cylc-install.conf``


The following Cylc commands will read Rose Suite Configurations:

- ``cylc validate``
- ``cylc graph``
- ``cylc list``
- ``cylc config``


Rose Config
-----------

.. attention::

   Rose configurations for Cylc **workflows** continue to be referred to
   as Rose **suites**.

A fuller description of
:ref:`rose suite config is available here<Rose Suites>`.

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


Special Variables
-----------------

The Cylc Rose plugin has specific logic for handling a small group of special
variables in the ``rose-suite.conf`` file:

``ROSE_ORIG_HOST``
   The plugin provides the hostname of the computer where the plugin runs as
   an evironment variable.

``ROSE_VERSION``
   The plugin provides ``ROSE_VERSION`` from your installed Rose Version
   in the environment section and any templating sections you have defined.

   .. deprecated:: 8.0.0

      Setting ``[env]ROSE_VERSION`` in ``rose-suite.conf``.

      With Cylc 7 / Rose2019 users could set ``ROSE_VERSION`` for thier
      suites. This is no longer possible, and if set in your
      ``ROSE_VERSION`` in your suite configuration it will be overwritten.

   you set ``ROSE_VERSION`` in your ``rose-suite.conf`` it will be replaced.

``CYLC_VERSION``
   The plugin will remove ``CYLC_VERSION`` from your config as it is provided
   by Cylc's config processing.

   .. deprecated:: 8.0.0

      Setting ``[env]CYLC_VERSION`` in ``rose-suite.conf``.

      With Cylc 7 / Rose2019 users could set ``CYLC_VERSION`` for thier
      suites. This is no longer possible, and if you set ``CYLC_VERSION``
      in your suite configuration will be overwritten.


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

For a workflow with the following definitions in the :term:`source directory`:

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


.. _rose-stem:

Rose Stem
=========

.. seealso::

   `Rose Stem documentation
   <https://metomi.github.io/rose/2019.01.2/html/tutorial/rose/furthertopics/
   rose-stem.html>`_


Cylc Rose provides a Rose Stem command, if FCM is installed on your system.
At Cylc 8 Rose Stem is a wrapper to ``cylc install`` rather than
``rose suite-run``.

Rose Stem is a wrapper around the ``cylc install`` command which
provides some additional Jinja2 variables.

Cylc 8 stores variables set by rose and rose-stem in the optional
configuration file ``~/cylc-run/my_workflow/opt/rose-suite-cylc-install.conf``.

.. caution::

   To reinstall a rose stem suite use ``cylc reinstall``.  Cylc can get any
   options you do not change from the ``rose-suite-cylc-install.conf``` file.
   Using ``rose stem`` a second time will attempt install a new copy
   of your rose stem suite.

"""

__version__ = '1.0.0.dev'
