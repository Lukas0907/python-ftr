# -*- coding: utf-8 -*-
u"""
Copyright 2015 Olivier Cortès <oc@1flow.io>.

This file is part of the python-ftr project.

python-ftr is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

python-ftr is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public
License along with python-ftr. If not, see http://www.gnu.org/licenses/


"""
import requests
import logging

from .config import ftr_get_config, SiteConfig, CACHE_TIMEOUT, cached
from .extractor import ContentExtractor
from sparks.utils.http import detect_encoding_from_requests_response

LOGGER = logging.getLogger(__name__)


@cached(timeout=CACHE_TIMEOUT)
def requests_get(url):
    """ Eventually cache the requests result. """

    LOGGER.info(u'Fetching %s…', url)
    return requests.get(url)


def ftr_process(url=None, content=None, config=None):
    """ process an URL, or some already fetched content from a given URL.

    This function is suitable for live extraction (content currently
    available on the internet), but also for postponed or post-mortem
    extraction (where the content was removed from the internet, but you
    still have the HTML and the original URL handy).

    :param url: The url of article to extract as an unicode string. Can be
        ``None``, but only if you provide both :param:`content` and
        :param:`config` arguments. Default: ``None``.

    :param content: the HTML content already downloaded, as string. If given,
        it will be used for extraction, and the :param:`url` will be used only
        for site config lookup. Default: ``None``.

    :param config: a Five Filter site config (as string or :class:`SiteConfig`
        instance). if None (eg. not given), it will be guessed from
        :param:`url` as well as possible. Default: ``None``.

    This function can raise some exceptions:

    - :class:`SiteConfigNotFound` if no five-filter site config can be found.
    - :class:`ContentExtractionException` if an error occured during
      content extraction.
    - any raw requests.* exception, network related, if anything goes
      wrong during url fetching.

    It will return:

    - either a :class:`ContentExtractor` instance with extracted
      attributes set, in case everything went OK.
    - or ``None``, if content was not given and url fetching returned a
      non-OK HTTP code, or if extraction (body or title) failed.
    """

    if url is None and content is None and config is None:
        raise RuntimeError('At least one of url or the couple content/config '
                           'argument must be present.')

    if content is not None and url is None and config is None:
        raise RuntimeError('Passing content only will not give any result.')

    if content is None:
        if url is None:
            raise RuntimeError('When content is unset, url must be set.')

        try:
            result = requests_get(url)

            if result.status_code != requests.codes.ok:
                LOGGER.error(u'Wrong status code in return while getting “%s”',
                             url)
                return None

            # Override before accessing result.text ; see `requests` doc.
            result.encoding = detect_encoding_from_requests_response(result)

            LOGGER.info(u'Downloaded %s bytes as %s text.',
                        len(result.text), result.encoding)

            # result.text is always unicode
            content = result.text

        except:
            LOGGER.error(u'Content could not be fetched from URL %s', url)
            raise

    if config is None:
        # This can eventually raise SiteConfigNotFound
        config = SiteConfig(site_config_text=ftr_get_config(url))

    extractor = ContentExtractor(config)

    if extractor.process(html=content):

        next_page_url = getattr(extractor, 'next_page_url', None)

        # This is recursive. Yeah.
        if next_page_url is not None:
            extractor.body += ftr_process(url=next_page_url).body

        return extractor

    return None
