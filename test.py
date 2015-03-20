#!env python
# -*- coding: utf-8 -*-
u""" Run a testsuite to check everything is OK in FTR. """

import sys
import os

# HEADS UP: this is needed before importing ftr for the module
#           to attach the SQLite handler before logging anything.
os.environ['FTR_TEST_ENABLE_SQLITE_LOGGING'] = '1'

import random
# import lxml.etree
import ftr
import ftr.config
from ftr.app import SQLiteHandler
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(SQLiteHandler(store_only=('siteconfig', ), clear_first=True))

FTR_SITECONFIG_PATH = os.environ.get(
    'FTR_SITECONFIG_PATH',
    os.path.expanduser(u'~/sources/ftr-site-config')
)


# Do not cache this, it's a generator and do not cost a lot, anyway.
# @ftr.config.cached(ftr.config.CACHE_TIMEOUT)
def load_test_urls():
    """ Yield all `test_url` directives values from all local siteconfig.

    If a siteconfig doesn't have any, a NoTestUrlException is yielded, not
    raised, for the caller to know it.
    """

    for url in (
        'http://www.lefigaro.fr/environnement/2011/11/10/01029-20111110ARTFIG00801-la-chine-confrontee-a-un-immense-defi-ecologique.php',  # NOQA
        'http://martinfowler.com/bliki/CertificationCompetenceCorrelation.html',
        'http://blogs.msdn.com/b/typescript/archive/2015/03/05/angular-2-0-built-on-typescript.aspx',  # NOQA
    ):
        yield url, None

    for root, dirs, files in os.walk(FTR_SITECONFIG_PATH):
        for filename in files:
            if filename.endswith('.txt'):
                with open(os.path.join(root, filename), 'rb') as f:
                    got_test_url = False
                    for line in f.readlines():
                        if line.startswith('test_url'):
                            key, value = [x.strip() for x in line.split(':', 1)]

                            yield value, filename[:-4]
                            got_test_url = True

                    if not got_test_url:
                        yield ftr.NoTestUrlException(filename, filename[:-4])


def test():
    """ Run all tests.

    Environment variables:

    - ``FTR_TEST_CONFIG_ALWAYS_RELOAD`` (default: no) set to anything to
      always reload siteconfigs. Use when you patch them to fix them one
      by one.
    - ``FTR_TEST_WARN_NOT_FOUND`` (default: no) set to anything to only warn
      about unmatched siteconfigs directives. default is to stop testing.
    """

    # Make ftr_get_config avoid hitting the cache to always load local files.
    if bool(os.environ.get('FTR_TEST_CONFIG_ALWAYS_RELOAD', 0)):
        ftr.config.FTR_CONFIG_ALWAYS_RELOAD = random.random()

    FTR_TEST_WARN_NOT_FOUND = bool(
        os.environ.get('FTR_TEST_WARN_NOT_FOUND', 0))

    if len(sys.argv) > 1:
        START_AT = int(sys.argv[1])
    else:
        START_AT = 0

    if START_AT > 0:
        LOGGER.info(u'Skipping until URL #%s…', START_AT)

    for index, item in enumerate(load_test_urls()):

        if index < START_AT:
            continue

        if isinstance(item, ftr.NoTestUrlException):
            LOGGER.critical(u'No test URL in %s!', item.filename,
                            extra={'siteconfig': item.siteconfig_name})
            continue

        url, siteconfig = item

        LOGGER.info(u'Testing URL #%s %s…', index, url,
                    extra={'siteconfig': siteconfig})

        try:
            extractor = ftr.process(url)

        except Exception:
            LOGGER.exception(u'Error while parsing %s', url,
                             extra={'siteconfig': siteconfig})
            continue

        if extractor is None:
            LOGGER.error(u'Network problem while extracting.',
                         extra={'siteconfig': siteconfig})
            continue

        assert bool(extractor.title) is True or FTR_TEST_WARN_NOT_FOUND
        assert bool(extractor.body) is True or FTR_TEST_WARN_NOT_FOUND

        if bool(extractor.config.author):
            assert bool(extractor.author) is True or FTR_TEST_WARN_NOT_FOUND

        if bool(extractor.config.date):
            assert bool(extractor.date) is True or FTR_TEST_WARN_NOT_FOUND

        if bool(extractor.config.next_page_link):
            assert bool(extractor.next_page_link) is True or FTR_TEST_WARN_NOT_FOUND  # NOQA

if __name__ == '__main__':
    test()
