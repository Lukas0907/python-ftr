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
import os
import re
import logging

from ordered_set import OrderedSet

try:
    from cacheops import cached

except ImportError:
    from functools import wraps

    def cached(*a, **kw):
        """ a no-op cache in case cacheops is not installed. """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

LOGGER = logging.getLogger(__name__)

# defaults to 3 days of caching for website configuration
CACHE_TIMEOUT = int(os.environ.get('PYTHON_FTR_CACHE_TIMEOUT', 345600))

HOSTNAME_REGEX = re.compile(
    r'/^(([a-z0-9-]*[a-z0-9])\.)*([a-z0-9-]*[a-z0-9])$/',
    re.IGNORECASE | re.UNICODE
)


class SiteConfigException(Exception):

    """ Abstract base class. """

    pass


class SiteConfigNotFound(SiteConfigException):

    """ Raised when no config can be found for a given website / url. """

    pass


class InvalidSiteConfig(SiteConfigException):

    """ Raised when an unrecoverable error is found in a site config. """

    pass


@cached(timeout=CACHE_TIMEOUT)
def ftr_get_config(website_url, exact_host_match=False):
    """ Download the Five Filters config from centralized repositories.

    The first entry found is returned. If no configuration is found,
    `None` is returned.

    If exact_host_match is True, we will not look for wildcard config
    matches. By default if host is 'test.example.org' we will look for
    and load '.example.org.txt' if it exists.

    .. todo:: there is currently no merging of site configs. In original
        FTR, primary and secondary configurations were merged. We could
        eventually re-implement this part if found useful.
    """

    import requests
    from sparks.utils.http import split_url

    repositories = [
        x.strip() for x in os.environ.get(
            'PYTHON_FTR_REPOSITORIES',
            u'https://raw.githubusercontent.com/1flow/ftr-site-config/master/ '
            u'https://raw.githubusercontent.com/fivefilters/ftr-site-config/master/'  # NOQA
        ).split() if x.strip() != u'']

    proto, host_and_port, remaining = split_url(website_url)

    host_domain_parts = host_and_port.split(u'.')

    # we don't store / use the “www.” part of domain name in siteconfig.
    if host_domain_parts[0] == u'www':
        host_domain_parts = host_domain_parts[1:]

    if exact_host_match:
        domain_names = [u'.'.join(host_domain_parts)]

    else:
        domain_names = [
            u'.'.join(host_domain_parts[-i:])
            for i in reversed(range(2, len(host_domain_parts) + 1))
        ]

    LOGGER.debug(u'Gathering configurations for domains %s from %s.',
                 domain_names, repositories)

    for repository in repositories:
        # try, in turn:
        #   website.ext.txt
        #   .website.ext.txt
        for domain_name in domain_names:

            skip_repository = False

            for full_name in (
                u'{0}{1}.txt'.format(repository, domain_name),
                u'.{0}{1}.txt'.format(repository, domain_name),
            ):
                result = requests.get(full_name)

                if result.status_code == requests.codes.ok:
                    if u'text/plain' not in result.headers.get('content-type') \
                        or u'<!DOCTYPE html>' in result.text \
                        or u'<html ' in result.text \
                            and u'</html>' in result.text:
                        LOGGER.error(u'“%s” repository URL does not return '
                                     u'RAW plain text results.')

                        skip_repository = True
                        break

                    LOGGER.info(u'Using siteconfig for domain %s from %s.',
                                domain_name, full_name)
                    return result.text

                if skip_repository:
                    break

            if skip_repository:
                break

    raise SiteConfigNotFound(
        u'No configuration found for domains {0} in repositories {1}'.format(
            u', '.join(domain_names), u', '.join(repositories)
        )
    )


def ftr_string_to_instance(config_string):
    """ Return a :class:`SiteConfig` build from the :param:`config_string`. """

    config = SiteConfig()

    for line_number, line_content in enumerate(
            config_string.strip().split(u'\n'), start=1):

        line_content = line_content.strip()

        # Skip empty lines & comments.
        if not line_content or line_content.startswith(u'#'):
            continue

        try:
            key, value = [
                x.strip() for x in line_content.strip().split(u':', 1)
            ]

        except:
            LOGGER.warning(u'Unrecognized syntax “%s” on line #%s.',
                           line_content, line_number)
            continue

        if not key or not value:
            LOGGER.warning(u'Empty key or value in “%s” on line #%s.',
                           line_content, line_number)
            continue

        # Commands for which we accept multiple statements.
        elif key in (
            'title', 'body', 'author', 'date',
            'strip', 'strip_id_or_class', 'strip_image_src',
            'single_page_link', 'single_page_link_in_feed',
            'next_page_link',
            'http_header',

            'find_string',
            'replace_string',

            'test_url',
            'test_contains',
            'test_title',
            'test_date',
            'test_author',
            'test_language',
        ):
            # Add to set, preserving order but squashing duplicates.
            getattr(config, key).add(value)

        # Single statement commands that evaluate to True or False.
        elif key in ('tidy', 'prune', 'autodetect_on_failure', ):
            setattr(config, key, bool(value))

        # Single statement commands stored as strings.
        elif key in ('parser', ):
            setattr(config, key, value)

        # The “replace_string(………): replace_value” one-liner syntax.
        elif key.startswith('replace_string(') and key.endswith(')'):
            # These 2 are lists, not sets.
            config.find_string.append(key[15:-1])
            config.replace_string.append(value)

        else:
            LOGGER.warning(u'Unsupported directive %s = %s on line #%s.',
                           key, value, line_number)

    find_count = len(config.find_string)
    replace_count = len(config.replace_string)

    if find_count != replace_count:
        raise InvalidSiteConfig(u'find_string and remplace_string do not '
                                u'correspond ({0} != {1})'.format(
                                    find_count, replace_count))

    return config


class SiteConfig(object):

    """ Holds extraction pattern and other directives for a given website.

    See ContentExtractor class to see how it's used.

    Five filters Site Config, ported to Python.

    Original was PHP, taken from
    https://github.com/wallabag/wallabag/blob/master/inc/3rdparty/libraries/content-extractor/SiteConfig.php  # NOQA

    @version 0.8
    @date 2013-04-16
    @author Keyvan Minoukadeh
    @copyright 2013 Keyvan Minoukadeh
    @license http://www.gnu.org/licenses/agpl-3.0.html AGPL v3
    """

    defaults = {
        'tidy': True,
        'parser': 'libxml',
        'prune': True,
        'autodetect_on_failure': True,
    }

    def __unicode__(self):
        """ Print title & body. """
        return u'title: %s, body: %s' % (self.title, self.body)

    def __init__(self, host=None, site_config_text=None):
        """ Load a first config, either from a hostname or a string config. """

        self.reset()

        if host is not None:
            self.load(host)

        if site_config_text is not None:
            self.append(ftr_string_to_instance(site_config_text))

    def reset(self):
        """ (re)set all attributes to defaults. """

        # Use first matching element as title (0 or more xpath expressions)
        self.title = OrderedSet()

        # Use first matching element as body (0 or more xpath expressions)
        self.body = OrderedSet()

        # Use first matching element as author (0 or more xpath expressions)
        self.author = OrderedSet()

        # Use first matching element as date (0 or more xpath expressions)
        self.date = OrderedSet()

        # Strip elements matching these xpath expressions (0 or more)
        self.strip = OrderedSet()

        # Strip 0 or more elements which contain these
        # strings in the id or class attribute.
        self.strip_id_or_class = OrderedSet()

        # Strip 0 or more images which contain
        # these strings in the src attribute.
        self.strip_image_src = OrderedSet()

        # Additional HTTP headers to send
        # NOT YET USED
        self.http_header = OrderedSet()

        # For those 3, None means that default will be used. But we need
        # None to distinguish from False during multiple configurations
        # merges.
        self.tidy = None
        self.prune = None
        self.autodetect_on_failure = None

        # Test URL - if present, can be used to test the config above
        self.test_url = OrderedSet()
        self.test_contains = OrderedSet()

        # Single-page link should identify a link element or URL pointing
        # to the page holding the entire article.
        #
        # This is useful for sites which split their articles across
        # multiple pages. Links to such pages tend to display the first
        # page with links to the other pages at the bottom.
        #
        # Often there is also a link to a page which displays the entire
        # article on one page (e.g. 'print view').
        #
        # `single_page_link` should be an XPath expression identifying the
        # link to that single page. If present and we find a match, we will
        # retrieve that page and the rest of the options in this config will
        # be applied to the new page.
        self.single_page_link = OrderedSet()

        self.next_page_link = OrderedSet()

        # Single-page link in feed? - same as above, but patterns applied
        # to item description HTML taken from feed. XXX
        self.single_page_link_in_feed = OrderedSet()

        # Which parser to use for turning raw HTML into a DOMDocument,
        # either `libxml` (PHP) / `lxml` (Python) or `html5lib`. Defaults
        # to `lxml` if None.
        self.parser = None

        # Strings to search for in HTML before processing begins. Goes by
        # pairs with `replace_string`. Not a set because we can have more
        # than one of the same, to be replaced by different values.
        self.find_string = []

        # Strings to replace those found in `find_string` before HTML
        # processing begins.
        self.replace_string = []

    def load(self, host, exact_host_match=False):
        """ Load a config for a hostname or url. """

        if not host.startswith(u'http://') and not host.startswith(u'https://'):
            # ftr_get_config() expects a full URL.
            host = u'http://' + host

        # Can raise a SiteConfigNotFound, intentionally bubbled.
        config = ftr_get_config(host, exact_host_match)

        if config is None:
            LOGGER.error(u'Error while loading configuration.')
            return

        self.append(ftr_string_to_instance(config))

    def append(self, newconfig):
        """ Append a dict()ified site config to current instance. """

        # Check for commands where we accept multiple statements (no test_url)
        for attr_name in (
            'title', 'body', 'author', 'date',
            'strip', 'strip_id_or_class', 'strip_image_src',
            'single_page_link', 'single_page_link_in_feed',
            'next_page_link', 'http_header'
        ):
            # Append to ordered set. We keep ordering, but no duplicates.
            current_set = getattr(self, attr_name)
            for val in getattr(newconfig, attr_name):
                # Too bad ordered set has no .union() method.
                current_set.add(val)
            setattr(self, attr_name, current_set)

        # Check for single statement commands;
        # we do not overwrite existing values.
        for attr_name in (
            'parser', 'tidy', 'prune', 'autodetect_on_failure'
        ):
            if getattr(self, attr_name) is None:
                if getattr(newconfig, attr_name) is None:
                    setattr(self, attr_name, self.defaults[attr_name])
                else:
                    setattr(self, attr_name, getattr(newconfig, attr_name))

        # HEADS UP: PHP → Python port.
        if self.parser == 'libxml':
            self.parser = 'lxml'

        for attr_name in ('find_string', 'replace_string', ):
            # Find/replace strings are lists, we extend.
            getattr(self, attr_name).extend(getattr(newconfig, attr_name))

        if self.find_string:
            # This will ease replacements in the extractor.
            self.replace_patterns = zip(
                self.find_string, self.replace_string)

        else:
            self.replace_patterns = None

    # method aliasing for API compatibility.
    merge = append
