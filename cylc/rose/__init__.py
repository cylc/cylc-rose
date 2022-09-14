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
Rose Suite Configurations
=========================

This plugin is activated by the existence of a Rose Suite Configuration file
(called ``rose-suite.conf``) in the workflow definition directory which allows
you to:

- Set template variables used in the workflow definition.
- Configure files to be installed via ``cylc install``.
- Define environment variables for the Cylc scheduler.

The following Cylc commands will read Rose Suite Configurations:

- ``cylc install``
- ``cylc validate``
- ``cylc graph``
- ``cylc list``
- ``cylc config``

.. Note::

   Cylc Rose allows ``cylc install`` to replace the ``rose suite-run``
   command (present in Rose versions 2019.01 and earlier).


Configuration File
------------------

.. attention::

   Although we now refer to Cylc **workflows** (rather than **suites**) we
   continue to refer to the ``rose-suite.conf`` file as a Rose Suite
   Configuration.

A fuller description of
:ref:`Rose Suite Configuration is available here<Rose Suites>`.

The following sections are permitted in the ``rose-suite.conf`` files:

.. csv-table::
   :header: config item, description

   ``opts=A B C``, A space limited list of optional configs.
   ``[env]``, "Variables which the cylc-rose plugin will export to the
   environment."
   ``[template variables]``, "Variables which can be used by Jinja2 or Empy
   in the workflow definition."
   ``[file:destination]``, A file from one or more sources to be installed.

.. note::

   For compatibility with Cylc 7, sections ``[suite.rc:empy]`` and
   ``[suite.rc:jinja2]`` will be processed, but are deprecated and provided
   for ease of porting Cylc 7 workflows.


Special Variables
-----------------

The Cylc Rose plugin provides two environment/template variables
to the Cylc scheduler:

``ROSE_ORIG_HOST``
   Cylc commands (such as ``cylc install``, ``cylc validate`` and
   ``cylc play``)
   will provide the name of the host on which the command is run.

   If the workflow is installed the value of ``ROSE_ORIG_HOST`` will be
   set in ``opt/rose-suite-cylc-install.conf`` and used by future commands
   e.g. ``cylc play``.

   Using ``cylc install`` should produce a more consistent value
   for ``ROSE_ORIG_HOST``; running Cylc commands on non-installed
   workflows may produce inconsistent values because the host
   is identified each time you run a command.


``ROSE_VERSION``
   When running Cylc commands such as ``cylc install``,
   ``cylc play`` and ``cylc validate``
   the plugin provides the version number of your installed Rose Version in
   workflow scheduler's environment.

   .. deprecated:: 8.0.0

      Setting ``[env]ROSE_VERSION`` in ``rose-suite.conf``.
      With Cylc 7 / Rose2019 users could set ``ROSE_VERSION`` for their
      suites. This is no longer possible, and if set in your
      ``ROSE_VERSION`` in your suite configuration it will be ignored.


``CYLC_VERSION``
   .. deprecated:: 8.0.0

      ``CYLC_VERSION`` will be removed from your configuration by the
      Cylc-Rose plugin, as it is now set by Cylc.

Additional CLI options
----------------------
You can use command line options to set or override
any setting you could put in a ``rose-suite.conf`` file: If you
have Cylc Rose installed see ``cylc install --help``.


Cylc Install Optional Config
----------------------------

If Cylc-Rose is installed, using ``cylc install`` with a workflow containing a
Rose Suite Configuration will write a record of command line options set in
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

__version__ = '1.1.1'
