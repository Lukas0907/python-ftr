# -*- coding: utf-8 -*-
u""" Python FTR content extractor class and utils.

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
import logging

try:
    from lxml import etree
    # from lxml.cssselect import CSSSelector
    from readability.readability import Document

except ImportError:
    # Avoid a crash during setup.py
    # In normal conditions where deps are installed, this should not happen.
    # Yeah I know it's an evil hack.
    pass

from StringIO import StringIO

LOGGER = logging.getLogger(__name__)

if bool(os.environ.get('FTR_TEST_ENABLE_SQLITE_LOGGING', False)):
    LOGGER.info(u'Activating SQL logger for FTR testing environment.')
    from ftr.app import SQLiteHandler
    LOGGER.addHandler(SQLiteHandler(store_only=('siteconfig', )))


try:
    import tidylib

except:
    LOGGER.warning('Please install the tidy library (eg. tidyhtml on Arch '
                   'Linux or libtidy-0.99-0 on Debian/Ubuntu). Things will '
                   'work without it, but results will be eventually better '
                   u'with it.')

    tidylib = None


class ContentExtractor(object):

    """
    Extract content from HTML, using patterns specified in site configuration.

    .. todo:: complete autodection port. As `1flow <http://1flow.io/>`_
        has its own autodetection code and FTR was primarily developed to
        be integrated in a complex parsing chain, I didn't reimplement
        all of the automatic extraction code here.

    Original PHP was version 1.0, written on 2013-02-05 by Keyvan Minoukadeh.
    """

    tidy_config = {
        'clean': True,
        'indent': 0,
        'output-xhtml': True,
        'logical-emphasis': True,
        'show-body-only': False,
        'new-blocklevel-tags':
            'article, aside, footer, header, hgroup, menu, '
            'nav, section, details, datagrid',
        'new-inline-tags': 'mark, time, meter, progress, data',
        'wrap': 0,
        'drop-empty-paras': True,
        'drop-proprietary-attributes': False,
        'enclose-text': True,
        'enclose-block-text': True,
        'merge-divs': True,
        'merge-spans': True,
        'char-encoding': 'utf8',
        'hide-comments': True
    }

    def __init__(self, config):
        """ Hello my dear pep257. This is an init, bright and shiny. """

        self.reset()

        self.config = config
        # LOGGER.info(u'Set config to %s.', config)

    def reset(self):
        """ (re)set all instance attributes to default.

        Every attribute is set to ``None``, except :attr:`author`
        and :attr:`failures` which are set to ``[]``.
        """

        self.config = None
        self.html = None
        self.parsed_tree = None
        self.tidied = False
        self.next_page_link = None
        self.title = None
        self.author = set()
        self.language = None
        self.date = None
        self.body = None
        self.failures = set()
        self.success = False

        LOGGER.debug(u'Reset extractor instance to defaults/empty.')

    def _process_replacements(self, html):
        """ Do raw string replacements on :param:`html`. """

        if self.config.find_string:
            for find_pattern, replace_pattern in self.config.replace_patterns:
                html = html.replace(find_pattern, replace_pattern)

            LOGGER.info(u'Done replacements.',
                        extra={'siteconfig': self.config.host})

        return html

    def _tidy(self, html, smart_tidy):
        """ Tidy HTML if we have a tidy method.

        This fixes problems with some sites which would otherwise trouble
        DOMDocument's HTML parsing.

        Although sometimes it makes the problem worse, which is why we can
        override it in site config files.
        """

        if self.config.tidy and tidylib and smart_tidy:

            try:
                document, errors = tidylib.tidy_document(html, self.tidy_config)

            except UnicodeDecodeError:
                # For some reason, pytidylib fails to decode, whereas the
                # original html content converts perfectly manually.
                document, errors = tidylib.tidy_document(html.encode('utf-8'),
                                                         self.tidy_config)
                document = document.decode('utf-8')
            # if errors:
            #     LOGGER.debug(u'Ignored errors returned by tidylib: %s',
            #                  errors)

            self.tidied = True
            self.html = document

            LOGGER.info(u'Tidied document.')

        else:
            self.html = html

    def _parse_html(self):
        """ Load the parser and parse `self.html`. """

        if self.config.parser != 'lxml':
            raise NotImplementedError('%s parser not implemented' %
                                      self.config.parser)

        self.parser = etree.HTMLParser()

        try:
            self.parsed_tree = etree.parse(StringIO(self.html), self.parser)

        except ValueError, e:
            if u'Unicode strings with encoding declaration are not supported' \
                    in unicode(e):

                # For some reason, the HTML/XML declares another encoding
                # in its meta tags. TODO: we should probably remove this
                # meta tag, because the sparks detection mechanism usually
                # does a pretty good job at finding it.
                #
                # For now, this will fail for anything other than utf-8 and
                # make the program crash.
                self.parsed_tree = etree.parse(StringIO(
                    self.html.encode('utf-8')), self.parser)

        # Wanna use CSS selector?
        #
        # td_empformbody = CSSSelector('td.empformbody')
        # for elem in td_empformbody(tree):
        #     # Do something with these table cells.

    def _extract_next_page_link(self):
        """ Try to get next page link. """

        # HEADS UP: we do not abort if next_page_link is already set:
        #           we try to find next (eg. find 3 if already at page 2).

        for pattern in self.config.next_page_link:
            items = self.parsed_tree.xpath(pattern)

            if not items:
                continue

            if len(items) == 1:
                item = items[0]

                if 'href' in item.keys():
                    self.next_page_link = item.get('href')

                else:
                    self.next_page_link = item.text.strip()

                LOGGER.info(u'Found next page link: %s.',
                            self.next_page_link)

                # First found link is the good one.
                break

            else:
                LOGGER.warning(u'%s items for next-page link %s',
                               items, pattern,
                               extra={'siteconfig': self.config.host})

    def _extract_title(self):
        """ Extract the title and remove it from the document.

        If title has already been extracted, this method will do nothing.

        If removal cannot happen or fails, the document is left untouched.
        """

        if self.title:
            return

        for pattern in self.config.title:
            items = self.parsed_tree.xpath(pattern)

            if not items:
                continue

            if isinstance(items, basestring):
                # In case xpath returns only one element.
                items = [items]

            if len(items) == 1:
                item = items[0]

                try:
                    self.title = item.text.strip()

                except AttributeError:
                    # '_ElementStringResult' object has no attribute 'text'
                    self.title = unicode(item).strip()

                LOGGER.info(u'Title extracted: “%s”.', self.title,
                            extra={'siteconfig': self.config.host})

                try:
                    item.getparent().remove(item)

                except TypeError:
                    # Argument 'element' has incorrect type (expected
                    # lxml.etree._Element, got _ElementStringResult)
                    pass

                except AttributeError, e:
                    if u'NoneType' not in unicode(e):
                        LOGGER.exception(u'Could not remove title from '
                                         u'document.',
                                         extra={'siteconfig': self.config.host})
                    # implicit: else: this is begnin

                except:
                    LOGGER.exception(u'Could not remove title from document.',
                                     extra={'siteconfig': self.config.host})

                # Exit at first item found.
                break

            else:
                LOGGER.warning(u'Multiple items (%s) for title pattern %s.',
                               items, pattern,
                               extra={'siteconfig': self.config.host})

    def _extract_author(self):
        """ Extract author(s) if not already done. """

        if bool(self.author):
            return

        for pattern in self.config.author:

            items = self.parsed_tree.xpath(pattern)

            if isinstance(items, basestring):
                # In case xpath returns only one element.
                items = [items]

            for item in items:

                if isinstance(item, basestring):
                    # '_ElementStringResult' object has no attribute 'text'
                    stripped_author = unicode(item).strip()

                else:
                    try:
                        stripped_author = item.text.strip()

                    except AttributeError:
                        # We got a <div>…
                        stripped_author = etree.tostring(item)

                if stripped_author:
                    self.author.add(stripped_author)
                    LOGGER.info(u'Author extracted: %s.', stripped_author,
                                extra={'siteconfig': self.config.host})

    def _extract_language(self):
        """ Extract language from the HTML ``<head>`` tags. """

        if self.language:
            return

        found = False

        for pattern in self.config.language:
            for item in self.parsed_tree.xpath(pattern):
                stripped_language = item.strip()

                if stripped_language:
                    self.language = stripped_language
                    LOGGER.info(u'Language extracted: %s.', stripped_language,
                                extra={'siteconfig': self.config.host})
                    found = True
                    break

            if found:
                break

    def _extract_date(self):
        """ Extract date from HTML. """

        if self.date:
            return

        found = False

        for pattern in self.config.date:

            items = self.parsed_tree.xpath(pattern)

            if isinstance(items, basestring):
                # In case xpath returns only one element.
                items = [items]

            for item in items:
                if isinstance(item, basestring):
                    # '_ElementStringResult' object has no attribute 'text'
                    stripped_date = unicode(item).strip()

                else:
                    try:
                        stripped_date = item.text.strip()

                    except AttributeError:
                        # .text is None. We got a <div> item with span-only
                        # content. The result will probably be completely
                        # useless to a python developer, but at least we
                        # didn't fail handling the siteconfig directive.
                        stripped_date = etree.tostring(item)

                if stripped_date:
                    # self.date = strtotime(trim(elems, "; \t\n\r\0\x0B"))
                    self.date = stripped_date
                    LOGGER.info(u'Date extracted: %s.', stripped_date,
                                extra={'siteconfig': self.config.host})
                    found = True
                    break

            if found:
                break

    def _strip_unwanted_elements(self):

        def _remove(xpath_expression):
            for item in self.parsed_tree.xpath(xpath_expression):
                item.getparent().remove(item)
                LOGGER.debug(u'Removed unwanted item %s.', item,
                             extra={'siteconfig': self.config.host})

        # Strip elements that use xpath expressions.
        for pattern in self.config.strip:
            _remove(pattern)

        # Strip elements using #id or .class attribute values.
        for pattern in self.config.strip_id_or_class:
            _remove(
                "//*[contains(@class, '{0}') or contains(@id, '{0}')]".format(
                    pattern.replace('"', '').replace("'", '')
                )
            )

        # Strip images using src attribute values.

        for pattern in self.config.strip_image_src:
            _remove(
                "//img[contains(@src, '{0}')]".format(
                    pattern.replace('"', '').replace("'", '')
                )
            )

        # Strip elements using Readability.com and Instapaper.com ignore
        # classes names .entry-unrelated and .instapaper_ignore
        # See https://www.readability.com/publishers/guidelines/#view-plainGuidelines  # NOQA
        # and http://blog.instapaper.com/post/730281947 for details.
        _remove(
            "//*[contains(concat(' ',normalize-space(@class),' ')"
            ",' entry-unrelated ') or contains(concat(' ',"
            "normalize-space(@class),' '),' instapaper_ignore ')]"
        )

        # Strip elements that contain style="display: none;".
        _remove("//*[contains(@style,'display:none')]")

    def _extract_body(self):
        """ Extract the body content from HTML. """

        def is_descendant_node(parent, node):
            node = node.getparent()
            while node is not None:
                if node == parent:
                    return True
                node = node.getparent()
            return False

        for pattern in self.config.body:
            items = self.parsed_tree.xpath(pattern)

            if len(items) == 1:
                if self.config.prune:
                    self.body = Document(etree.tostring(items[0])).summary()

                else:
                    self.body = etree.tostring(items[0])

                # We've got a body now.
                break

            else:
                appended_something = False
                body = etree.Element("root")

                for item in items:
                    if item.getparent() is None:
                        continue

                    is_descendant = False

                    for parent in body:
                        if (is_descendant_node(parent, item)):
                            is_descendant = True
                            break

                    if not is_descendant:

                        if self.config.prune:

                            # Clean with readability. Needs
                            # to-string conversion first.
                            pruned_string = Document(
                                etree.tostring(item)).summary()

                            # Re-parse the readability string
                            # output and include it in our body.
                            new_tree = etree.parse(
                                StringIO(pruned_string), self.parser)

                            failed = False

                            try:
                                body.append(
                                    new_tree.xpath('//html/body/div/div')[0]
                                )
                            except IndexError:

                                if 'id="readabilityBody"' in pruned_string:
                                    try:
                                        body.append(
                                            new_tree.xpath('//body')
                                        )
                                    except:
                                        failed = True

                                else:
                                    failed = True

                            if failed:
                                LOGGER.error(u'Pruning item failed:'
                                             u'\n\n%s\n\nWe got: “%s” '
                                             u'and skipped it.',
                                             etree.tostring(
                                                 item).replace(u'\n', u''),
                                             pruned_string.replace(u'\n', u''),
                                             extra={'siteconfig':
                                                    self.config.host})
                                pass

                        else:
                            body.append(item)

                        appended_something = True

                if appended_something:
                    self.body = etree.tostring(body)

                    # We've got a body now.
                    break

    def _auto_extract_if_failed(self):
        """ Try to automatically extract as much as possible. """

        if not self.config.autodetect_on_failure:
            return

        readabilitized = Document(self.html)

        if self.title is None:
            if bool(self.config.title):
                self.failures.add('title')

            title = readabilitized.title().strip()

            if title:
                self.title = title
                LOGGER.info(u'Title extracted in automatic mode.',
                            extra={'siteconfig': self.config.host})

            else:
                self.failures.add('title')

        if self.body is None:
            if bool(self.config.body):
                self.failures.add('body')

            body = readabilitized.summary().strip()

            if body:
                self.body = body
                LOGGER.info(u'Body extracted in automatic mode.',
                            extra={'siteconfig': self.config.host})

            else:
                self.failures.add('body')

        for attr_name in ('date', 'language', 'author', ):
            if not bool(getattr(self, attr_name, None)):
                if bool(getattr(self.config, attr_name, None)):
                    self.failures.add(attr_name)
                    LOGGER.warning(u'Could not extract any %s from XPath '
                                   u'expression(s) %s.', attr_name,
                                   u', '.join(getattr(self.config, attr_name)),
                                   extra={'siteconfig': self.config.host})
                    # import ipdb; ipdb.set_trace()

    def process(self, html, url=None, smart_tidy=True):
        u""" Process HTML content or URL.

        For automatic extraction patterns and cleanups, :mod:`readability-lxml`
        is used, to stick as much as possible to the original PHP
        implementation and produce at least similar results with the same
        site config on the same article/content.

        :param html: an unicode string containing a full HTML page content.
            Expected to have a ``DOCTYPE`` and all other standard
            attributes ; eg. HTML fragments are not supported.
            It will be replaced, tidied, cleaned, striped, and all
            metadata and body attributes will be extracted from it.
            Beware : this HTML piece will be mauled. See source code for
            exact processing workflow, it's quite gorgeous.
        :type html: unicode

        :param url: as of version 0.5, this parameter is ignored. (**TODO**)
        :type url: str, unicode or ``None``

        :param smart_tidy: When ``True`` (default), runs :mod:`pytidylib`
            to tidy the HTML, after after run ``find_string``/``replace_string``
            replacements and before running extractions.
        :type smart_tidy: bool

        :returns: ``True`` on success, ``False`` on failure.
        :raises:
            - :class:`RuntimeError` if config has not been set at
              instantiation. This should change in the future by looking
              up a config if an ``url`` is passed as argument.

        .. note:: If tidy is used and no result is produced, we will try
            again without tidying.
            Generally speaking, tidy helps us deal with PHP's patchy HTML
            parsing (LOOOOOL. Zeriously?) most of the time but it has
            problems of its own which we try to avoid with this option.
            In the Python implementation, `pytidylib` has showed to help
            sanitize a lot the HTML before processing it. But nobody's
            perfect, and errors can happen in the Python world too, thus
            the *tidy* behavior was thought sane enough to be keep.
        """

        # TODO: re-implement URL handling with self.reset() here.

        if self.config is None:
            raise RuntimeError(u'extractor site config is not set.')

        # TODO: If re-running ourselves over an already-replaced string,
        #       this should just do nothing because everything has been
        #       done. We should have a test for that.
        html = self._process_replacements(html)

        # We keep the html untouched after replacements.
        # All processing happens on self.html after this point.
        self._tidy(html, smart_tidy)

        # return

        self._parse_html()

        self._extract_next_page_link()

        self._extract_title()

        self._extract_author()

        self._extract_language()

        self._extract_date()

        self._strip_unwanted_elements()

        self._extract_body()

        # TODO: re-implement auto-detection here.
        # NOTE: hNews extractor was here.
        # NOTE: instapaper extractor was here.

        self._auto_extract_if_failed()

        if self.title is not None or self.body is not None \
            or bool(self.author) or self.date is not None \
                or self.language is not None:
            self.success = True

        # if we've had no success and we've used tidy, there's a chance
        # that tidy has messed up. So let's try again without tidy...
        if not self.success and self.tidied and smart_tidy:
            self.process(html, url=None, smart_tidy=False)

        return self.success
