#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Python Five-Filters setup.py. """

import sys

from setuptools import setup, find_packages

if '.' in sys.path:
    sys.path.remove('.')

# We want to be sure that Python will import the sparks from here, and not
# the one eventually installed system-wide or in the current virtualenv.
sys.path.insert(0, '.')

from ftr import version

setup(
    name="ftr",
    version=version,
    author="Olivier Cortès",
    author_email="contact@oliviercortes.com",
    description="HTML Article cleaner / extractor, Five-Filters compatible.",
    url="https://github.com/1flow/python-ftr",
    packages=find_packages(),
    dependency_links=[
        'https://github.com/1flow/sparks/tarball/master#egg=sparks',
    ],
    install_requires=[
        # 'html5lib',
        'pytidylib',
        'lxml',
        'ordered-set',
        'readability-lxml',
        'requests',
    ],
    extras_require={
        'cache':  ['cacheops'],
    },
    keywords=(
        'parsing',
        'websites',
        'articles',
    ),
    license='AGPLv3',
    long_description=(
        "The [cache] variant is suited for django+celery setups where "
        "Redis is available. It will cache website configs in Redis. "
        "This module does not currently implement automatic extraction "
        "(eg. without a website configuration). When it was ported from "
        "PHP, its main purpose was to be integrated in a wider chain "
        "That already does automatic extraction."
    )
)
