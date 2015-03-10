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
import logging
from lxml import etree
# from lxml.cssselect import CSSSelector
from readability.readability import Document
from StringIO import StringIO

LOGGER = logging.getLogger(__name__)


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

    .. todo:: autodection port. As 1flow has its own autodetection code,
        I didn't reimplement the autodection code here. I use this class
        for configured parsing only.

    Original (PHP) version info:

    @version 1.0
    @date 2013-02-05
    @author Keyvan Minoukadeh
    @copyright 2013 Keyvan Minoukadeh
    @license http://www.gnu.org/licenses/agpl-3.0.html AGPL v3

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
        """ (re)set all instance attributes to default. """

        self.config = None
        self.html = None
        self.parsed_tree = None
        self.tidied = False
        self.next_page_url = None
        self.title = None
        self.author = []
        self.language = None
        self.date = None
        self.body = None
        self.failures = []
        self.success = False

        LOGGER.debug(u'Reset extractor instance to defaults/empty.')

    def _process_replacements(self, html):
        """ Do raw string replacements on :param:`html`. """

        if self.config.find_string:
            for find_pattern, replace_pattern in self.config.replace_patterns:
                html = html.replace(find_pattern, replace_pattern)

            LOGGER.info(u'Done replacements.')

        return html

    def _tidy(self, html, smart_tidy):
        """ Tidy HTML if we have a tidy method.

        This fixes problems with some sites which would otherwise trouble
        DOMDocument's HTML parsing.

        Although sometimes it makes the problem worse, which is why we can
        override it in site config files.
        """

        if self.config.tidy and tidylib and smart_tidy:

            document, errors = tidylib.tidy_document(html, self.tidy_config)

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
        self.parsed_tree = etree.parse(StringIO(self.html), self.parser)

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
                    self.next_page_url = item.values()[0]

                else:
                    self.next_page_url = item.text.strip()

                # First found link is the good one.
                break

            else:
                LOGGER.warning(u'%s items for next-page link %s',
                               items, pattern)

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

            if len(items) == 1:
                item = items[0]
                self.title = item.text

                LOGGER.info(u'title set to “%s”', self.title)

                try:
                    item.getparent().remove(item)

                except:
                    LOGGER.exception(u'Could not remove title from document.')

                # Exit at first item found.
                break

            else:
                LOGGER.warning(u'%s items for title %s',
                               items, pattern)

    def _extract_author(self):
        """ Extract author(s) if not already done. """

        if self.author:
            return

        for pattern in self.config.author:
            for item in self.parsed_tree.xpath(pattern):
                stripped_author = item.text.strip()

                if stripped_author:
                    self.author.append(stripped_author)
                    LOGGER.info(u'Author found: %s', stripped_author)

    def _extract_language(self):
        """ Extract language from the HTML ``<head>`` tags. """

        if self.language:
            return

        found = False

        for pattern in (
            '//html[@lang]/@lang',
            '//meta[@name="DC.language"]/@content',
        ):
            for item in self.parsed_tree.xpath(pattern):
                stripped_language = item.strip()

                if stripped_language:
                    self.language = stripped_language
                    LOGGER.info(u'Language found: %s', stripped_language)
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
            for item in self.parsed_tree.xpath(pattern):
                stripped_date = item.text.strip()

                if stripped_date:
                    # self.date = strtotime(trim(elems, "; \t\n\r\0\x0B"))
                    self.date = stripped_date
                    LOGGER.info(u'Date found: %s', stripped_date)
                    found = True
                    break

            if found:
                break

    def _strip_unwanted_elements(self):

        def _remove(xpath_expression):
            for item in self.parsed_tree.xpath(xpath_expression):
                item.getparent().remove(item)
                LOGGER.debug(u'Removed unwanted item %s', item)

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
            while node:
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

                    for parent in self.body:
                        if (is_descendant_node(parent, item)):
                            is_descendant = True
                            break

                    if not is_descendant:
                        if self.config.prune:
                            etree.SubElement(
                                body,
                                etree.parse(Document(item).summary(),
                                            self.parser)
                            )

                        else:
                            etree.SubElement(body, item)

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
            if self.config.title is not None:
                self.failures.append('title')

            title = readabilitized.title().strip()

            if title:
                self.title = title
                LOGGER.info(u'Got a title in automatic mode.')

        if self.body is None:
            if self.config.body is not None:
                self.failures.append('body')

            body = readabilitized.summary().strip()

            if body:
                self.body = body

                LOGGER.info(u'Extracted a body in automatic mode.')

    def process(self, html, url=None, smart_tidy=True):
        """ Process HTML content or URL.

        Returns True on success, False on failure.

        :param:`smart_tidy` indicates that if tidy is used and no results
        are produced, we will try again without it. Tidy helps us deal
        with PHP's patchy HTML parsing (LOOOOOL. Zeriously?) most of the
        time but it has problems of its own which we try to avoid with
        this option.
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
            or self.author is not None or self.date is not None \
                or self.language is not None:
            self.success = True

        # if we've had no success and we've used tidy, there's a chance
        # that tidy has messed up. So let's try again without tidy...
        if not self.success and self.tidied and smart_tidy:
            self.process(html, url=None, smart_tidy=False)

        return self.success
