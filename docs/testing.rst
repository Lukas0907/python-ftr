.. Python FTR documentation master file, created by
   sphinx-quickstart on Tue Mar 10 09:11:24 2015.


Python FTR testsuite
====================

The python FTR module includes a testsuite to validate all ``siteconfigs``
files and check they are up-to-date. It's composed of:

- a python script to gather all `test_url` lines and run the extractor on them.
- a light `Flask <http://flask.pocoo.org>`_ web application to visualize the
  log results and edit the siteconfigs more easily on github.

To run the testsuite::

    # Wherever you cloned the python-ftr source repository
    cd ~/path/to/python-ftr

    # See below for conventions and meanings
    export FTR_TEST_WARN_NOT_FOUND=1
    export PYTHON_FTR_SOURCE_PATH=`pwd`
    export FTR_SITECONFIG_PATH=`wherever_your_siteconfigs_repository_lies`

    # install requirements
    pip install -r docs-requirements

    # let the extractors flow in one shell
    python test.py

    # run the webapp in another
    python ftr/app/__init__.py


Then head to `localhost:5000 <http://localhost:5000>`_ to see the results.

You can easily run the testsuite in a cron job. It will clear the logs at
every start, so if you want to get an history, you will need to rotate the
SQLite database in you cronjob.



Testsuite arguments
-------------------

For now the :file:`test.py` only accepts an integer argument, which represents
the siteconfig index you want to start from. It is useful when a siteconfig
crashed or failed extracting. You can alter it and restart the testsuite at the
exact location it failed. Usage::

    # Will start the TS at item #123
    python test.py 123

Look at the testsuite console log for siteconfig indexes.


Testsuite environment variables
-------------------------------

- ``FTR_TEST_WARN_NOT_FOUND``: when enabled, allows the testsuite to process
  every siteconfig / test_url without stopping. When disabled (the default),
  the testsuite will halt at the first metadata attribute that cannot be
  extracted. This allows to fix bugs / XPath expressions one by one, but it's
  necessarily what you want if you plan to run the TS web application.

- ``PYTHON_FTR_SOURCE_PATH``: the full path where you cloned the FTR
  repository. This variable is used to configure the SQL logging handler.
  Defaults to :file:`~/sources/python-ftr`.

- ``FTR_SITECONFIG_PATH``: the full path where you cloned the siteconfigs
  repository. Its used to gather all ``test_url`` to feed the testsuite.
  Defaults to :file:`~/sources/ftr-site-config`.

- ``FTR_TEST_CONFIG_ALWAYS_RELOAD``: When the cache is enabled, this variable
  allows to not cache siteconfig files (we still cache fetched URLs). It is
  useful when you run the tests on your own and manually edit siteconfig files
  to rapidly test modifications locally before submitting PRs. Default: unset,
  thus siteconfig files are reloaded only when the cache expires (eg. 3 days).

- ``FTR_TEST_ENABLE_SQLITE_LOGGING``: **this variable is internal, do
  not touch it at all**. The test script manages it alone, and use it to enable the
  SQL logging everywhere in `ftr`. In normal conditions, SQL logging is
  disabled for obvious performance reasons.
