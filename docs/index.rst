.. Python FTR documentation master file, created by
   sphinx-quickstart on Tue Mar 10 09:11:24 2015.

Welcome to Python FTR's documentation!
======================================

FTR is a *partial* (re-)implementation of the `Five-Filters extractor
<http://fivefilters.org/>`_ in Python.

It cleans up HTML web pages and extract their content and metadata for a
more comfortable reading experience (or whatever you need it for). It uses
a centralized and mutualized repository of configuration files to parse
websites at the most precise level possible, and fallbacks to the well-known
`readability` automatic extractor if no configuration is found.

A notable difference is that this python implementation will fetch the
website configuration from a centralized repository on the internet on the
fly if no configuration is found locally.


Table of Contents
-----------------

.. toctree::
   :maxdepth: 2

   install
   process
   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

