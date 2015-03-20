
===============================
Python-FTR Installation / Setup
===============================

Package installation
====================

To install latest stable version published, do it with PIP::

	pip install ftr


.. warning:: This is currently broken du to external dependancies not yet
	packaged. See `related issue <https://github.com/1flow/python-ftr/issues/4>`_
	for details.



Or install directly via github::

	# dependancies
	pip install git+https://github.com/Karmak23/humanize.git@master#egg=humanize
	pip install git+https://github.com/1flow/sparks.git@master#egg=sparks

	# Python-FTR itself
	pip install git+https://github.com/1flow/python-ftr.git@master#egg=ftr



Using a cache system
--------------------

If you are using :mod:`ftr` in a Django project, you can benefit from :mod:`cacheops`
to avoid repetitive fetching of website configuration files. Install it this way::

	pip install cacheops


And configure `cacheops` `as usual <https://github.com/Suor/django-cacheops>`_.



Configuration
=============



Environment variables
---------------------


- ``PYTHON_FTR_CACHE_TIMEOUT``: optional, in seconds, as an integer. The
  caching time of websites configuration files. Defaults to 3 days. Not
  used if cache is not available.
- ``PYTHON_FTR_REPOSITORIES``: one or more URLs, separated by spaces. In
  case you need a space in the URL itself, urlencode() it (eg. ``%2f``).

  Default values include an arbitrary local path ``${HOME}/sources/ftr-site-config``,
  the `1flow repository <https://github.com/1flow/ftr-site-config>`_ and the
  `Five-Filters repository <https://github.com/fivefilters/ftr-site-config>`_
  (see below for details / format).



Local configuration repositories
--------------------------------

Local siteconfig repositories are symply a complete or partial clone of any
online official git repository. Just clone one of them locally, make its
path first in the environment variable, and you're done if you just need to
override siteconfigs with local changes.


Website configuration repositories
----------------------------------

If there are more than one repository, they will be tried in turn ; first
match wins.

Web repositories must give access to raw siteconfig TXT format (eg a
`text/plain` download. There is partial test against failure on this side
in the code, but beware it's relatively weak. If the repository does not
return `text/plain` results, it will be ignored.

Eg. to use the filters from the
`1flow official repository <https://github.com/1flow/ftr-site-config>`_,
we use the following URL::

	https://raw.githubusercontent.com/1flow/ftr-site-config/master/




Usage
=====

When you're done installing and configuring, head to
`process documentation <process>`_ for simple wrapped usage, or consult
the whole API documentation for a customized one.
