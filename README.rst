#######
sabacan
#######

Sabacan is a command line interface using various application server APIs.
Currently sabacan support the following server APIs.

* `PlantUML Server`_
* `RedPen Server`_

Sabacan has the following design concept:

* **Command line option compatibility**. All subcommand options are compatible
  to the options of CLI commands corresponding to application servers.
  This ease to replace using the commands by sabacan.
* **Minimum dependencies**. Sabacan uses only Python standard libraries.
  This ease to export sabacan into environments unavailable to use package
  managers.

.. _PlantUML Server: http://plantuml.com/
.. _RedPen Server: http://redpen.cc/

Installation
============

Use pip::

    pip install sabacan

or use setup.py::

    python3 setup.py install

These will install sabacan command.

Usage
=====

Sabacan command takes a subcommand.

Generate UML by PlanUML server::

    sabacan -u http://localhost/plantuml plantuml -tpng sequence.uml

Validate document by RedPen::

    sabacan -u http://X.X.X.X redpen -r json document.md

Enable to specify the server URL by environment variables::

    export SABACAN_REDPEN_URL=http://localhost/redpen:8080
    sabacan redpen -r plain2 document.rst
    sabacan redpen -r xml document.txt
