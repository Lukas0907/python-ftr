# -*- coding: utf-8 -*-
u""" Python FTR configuration class and utils.

The configuration files are named “ siteconfig ” in Five Filters
terminology, and probably stands for “ website configuration ” sets.

A `siteconfig` is a simple text file with a ``key: value`` format.
These files are loaded into :class:`SiteConfig` instances. They are
named after the website they hold rules for.

.. Copyright 2015 Olivier Cortès <oc@1flow.io>.

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
import codecs
import logging

LOGGER = logging.getLogger(__name__)

if bool(os.environ.get('FTR_TEST_ENABLE_SQLITE_LOGGING', False)):
    from ftr.app import SQLiteHandler
    LOGGER.addHandler(SQLiteHandler(store_only=('siteconfig', )))

try:
    import requests
    from ordered_set import OrderedSet
    from sparks.utils.http import split_url

except ImportError:
    # Avoid a crash during setup.py
    # In normal conditions where deps are installed, this should not happen.
    # Yeah I know it's an evil hack.
    pass

try:
    from cacheops import cached

except Exception, e:
    LOGGER.warning(u'Cacheops seems not installed or not importable '
                   u'(exception was: %s). Running without cache.', e)
    from functools import wraps

    def cached(*a, **kw):
        """ A no-op decorator in case :mod:`cacheops` is not installed. """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


# defaults to 3 days of caching for website configuration
CACHE_TIMEOUT = int(os.environ.get('PYTHON_FTR_CACHE_TIMEOUT', 345600))

# test.py will set this to any random integer to fake cache
# invalidation without invalidating the fetched HTML pages.
FTR_CONFIG_ALWAYS_RELOAD = 0

HOSTNAME_REGEX = re.compile(
    r'/^(([a-z0-9-]*[a-z0-9])\.)*([a-z0-9-]*[a-z0-9])$/',
    re.IGNORECASE | re.UNICODE
)


class SiteConfigException(Exception):

    """ Abstract base class for all :class:`SiteConfig` related exceptions.

    Never raised directly, but you can catch it in an `except` block to
    get them all at once.
    """

    pass


class SiteConfigNotFound(SiteConfigException):

    """ Raised when no site config can be found for a given website or url. """

    pass


class InvalidSiteConfig(SiteConfigException):

    """ Raised when an unrecoverable error is found in a site config.

    Eg. when it has a very bad syntax error or a missing mandatory directive.

    As of version 0.5, all directives are optional, thus this exception
    is raised only in case of a non-matching number of ``find_string``
    / ``replace_string`` pairs. This could change in the future.
    """

    pass


class NoTestUrlException(SiteConfigException):

    """ Raised when a site config does not contain any test URL. """

    def __init__(self, filename, siteconfig_name, *args, **kwargs):
        """ pep257, you know how MUCH I love you. """
        self.filename = filename
        self.siteconfig_name = siteconfig_name

        super(NoTestUrlException, self).__init__(*args, **kwargs)


@cached(timeout=CACHE_TIMEOUT, extra=FTR_CONFIG_ALWAYS_RELOAD)
def ftr_get_config(website_url, exact_host_match=False):
    """ Download the Five Filters config from centralized repositories.

    Repositories can be local if you need to override siteconfigs.

    The first entry found is returned. If no configuration is found,
    `None` is returned. If :mod:`cacheops` is installed, the result will
    be cached with a default expiration delay of 3 days.

    :param exact_host_match: If ``False`` (default), we will look for
        wildcard config matches. For example if host is
        ``www.test.example.org``, we will try looking up
        ``test.example.org`` and ``example.org``.
    :param exact_host_match: bool

    :param website_url: either a full web URI (eg.
        ``http://www.website.com:PORT/path/to/a/page.html``) or simply
        a domain name (eg. ``www.website.com``). In case of a domain name,
        no check is performed yet, be careful of what you pass.
    :type website_url: str or unicode

    :returns: tuple -- the loaded site config (as unicode string) and
        the hostname matched (unicode string too).
    :raises: :class:`SiteConfigNotFound` if no config could be found.

    .. note:: Whatever ``exact_host_match`` value is, the ``www`` part is
        always removed from the URL or domain name.

    .. todo:: there is currently no merging/cascading of site configs. In
        the original Five Filters implementation, primary and secondary
        configurations were merged. We could eventually re-implement this
        part if needed by someone. PRs welcome as always.
    """

    def check_requests_result(result):
        return (
            u'text/plain' in result.headers.get('content-type')
            and u'<!DOCTYPE html>' not in result.text
            and u'<html ' not in result.text
            and u'</html>' not in result.text
        )

    repositories = [
        x.strip() for x in os.environ.get(
            'PYTHON_FTR_REPOSITORIES',
            os.path.expandvars(u'${HOME}/sources/ftr-site-config') + u' '
            + u'https://raw.githubusercontent.com/1flow/ftr-site-config/master/ '  # NOQA
            + u'https://raw.githubusercontent.com/fivefilters/ftr-site-config/master/'  # NOQA
        ).split() if x.strip() != u'']

    try:
        proto, host_and_port, remaining = split_url(website_url)

    except:
        host_and_port = website_url

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

            for txt_siteconfig_name in (
                u'{0}.txt'.format(domain_name),
                u'.{0}.txt'.format(domain_name),
            ):
                if repository.startswith('http'):
                    siteconfig_url = repository + txt_siteconfig_name

                    result = requests.get(siteconfig_url)

                    if result.status_code == requests.codes.ok:
                        if not check_requests_result(result):
                            LOGGER.error(u'“%s” repository URL does not '
                                         u'return text/plain results.')
                            skip_repository = True
                            break

                        LOGGER.info(u'Using remote siteconfig for domain '
                                    u'%s from %s.', domain_name,
                                    siteconfig_url, extra={
                                        'siteconfig': domain_name})
                        return result.text, txt_siteconfig_name[:-4]

                else:
                    filename = os.path.join(repository, txt_siteconfig_name)

                    if os.path.exists(filename):
                        LOGGER.info(u'Using local siteconfig for domain '
                                    u'%s from %s.', domain_name,
                                    filename, extra={
                                        'siteconfig': domain_name})

                        with codecs.open(filename, 'rb', encoding='utf8') as f:
                            return f.read(), txt_siteconfig_name[:-4]

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
    """ Return a :class:`SiteConfig` built from a ``config_string``.

    Simple syntax errors are just plainly ignored, and logged as warnings.

    :param config_string: a full site config file, raw-loaded from storage
        with something like
        ``config_string = open('path/to/site/config.txt', 'r').read()``.
    :type config_string: str or unicode

    :returns: a :class:`SiteConfig` instance.
    :raises: :class:`InvalidSiteConfig` in case of an unrecoverable error.

    .. note:: See the source code for supported directives names.
    """

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

        # handle some very rare title()d directives.
        key = key.lower()

        if not key or (not value and key != 'replace_string'):
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

            if key.endswith(u'_string'):
                # Append to list. Duplicites are allowed.
                getattr(config, key).append(value)

            else:
                # Add to set, preserving order but squashing duplicates.
                getattr(config, key).add(value)

        # Single statement commands that evaluate to True or False.
        elif key in ('tidy', 'prune', 'autodetect_on_failure', ):

            if value.lower() in ('no', 'false', '0', ):
                setattr(config, key, False)

            else:
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
            LOGGER.warning(u'Unsupported directive “%s” on line #%s.',
                           line_content, line_number)

    find_count = len(config.find_string)
    replace_count = len(config.replace_string)

    if find_count != replace_count:
        raise InvalidSiteConfig(u'find_string and remplace_string do not '
                                u'correspond ({0} != {1})'.format(
                                    find_count, replace_count))

    return config


class SiteConfig(object):

    """ Holds extraction pattern and other directives for a given website.

    See :class:`ContentExtractor` class to see how it's used.

    This is the Five Filters SiteConfig object, ported to Python.

    Original was PHP, version 0.8, written by Keyvan Minoukadeh.
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
        """ Load a first config, either from a string config or a hostname.

        If both are not empty, only `site_config_text` is used (eg. `host`
        is stored but is used to load a siteconfig).
        """

        self.reset()

        # This `host` attribute will become the
        # `siteconfig` extra argument in logging calls.
        self.host = host

        # We load only one of them, not both.
        # site_config_text has precedence for easy overriding.
        if site_config_text is None:
            if host is not None:
                self.load(host)

        else:
            self.append(ftr_string_to_instance(site_config_text))

    def reset(self):
        """ (re)set all attributes to defaults (eg. empty sets or ``None``). """

        # Use first matching element as title (0 or more xpath expressions)
        self.title = OrderedSet()

        # Use first matching element as body (0 or more xpath expressions)
        self.body = OrderedSet()

        # Use first matching element as author (0 or more xpath expressions)
        self.author = OrderedSet()

        # Use first matching element as date (0 or more xpath expressions)
        self.date = OrderedSet()

        # Put language here. It's not supported in siteconfig syntax,
        # but having it here allows more generic handling in extractor.
        self.language = (
            '//html[@lang]/@lang',
            '//meta[@name="DC.language"]/@content',
        )

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
        """ Load a config for a hostname or url.

        This method calls :func:`ftr_get_config` and :meth`append`
        internally. Refer to their docs for details on parameters.
        """

        # Can raise a SiteConfigNotFound, intentionally bubbled.
        config_string, host_string = ftr_get_config(host, exact_host_match)

        if config_string is None:
            LOGGER.error(u'Error while loading configuration.',
                         extra={'siteconfig': host_string})
            return

        self.append(ftr_string_to_instance(config_string))

    def append(self, newconfig):
        """ Append another site config to current instance.

        All ``newconfig`` attributes are appended one by one to ours.
        Order matters, eg. current instance values will come first when
        merging.

        Thus, if you plan to use some sort of global site config with
        more generic directives, append it last for specific directives
        to be tried first.

        .. note:: this method is also aliased to :meth:`merge`.
        """

        # Check for commands where we accept multiple statements (no test_url)
        for attr_name in (
            'title', 'body', 'author', 'date',
            # `language` is fixed in reset() and
            # not supported in siteconfig syntax.
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
