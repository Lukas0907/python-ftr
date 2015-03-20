# -*- coding: utf-8 -*-
u""" Flask app & SQLite logging handler.

from https://github.com/amka/SQLiteHandler

#
# Found it in the internet and modified for my own
# Amka [meamka@ya.ru]
#

"""

import os
import json
import time
import logging
import sqlite3

from lxml import etree
from ordered_set import OrderedSet
from datetime import datetime
from humanize.time import naturaldelta
from flask import Flask, render_template
from sqlalchemy import create_engine, MetaData, Table

PYTHON_FTR_SOURCE_PATH = os.environ.get(
    'PYTHON_FTR_SOURCE_PATH',
    os.path.expanduser(u'~/sources/python-ftr')
)

SQLITE_LOG_PATH = os.path.join(PYTHON_FTR_SOURCE_PATH, 'log.sqlite')

engine = create_engine('sqlite:///{0}'.format(SQLITE_LOG_PATH),
                       convert_unicode=True)
metadata = MetaData(bind=engine)
app = Flask(__name__)

LOGGER = logging.getLogger(__name__)


class OrderedEncoder(json.JSONEncoder):

    """ JSON Encode OrderedSet & LXML Element.

    OrderedSet are turned into lists, Elements are turned into strings.

    This encoder is suited to store logging messages into SQLite.
    """

    def default(self, obj):
        if isinstance(obj, OrderedSet):
            return list(obj)
        if isinstance(obj, etree._Element):
            return etree.tostring(obj)
        return json.JSONEncoder.default(self, obj)


class SQLiteHandler(logging.Handler):

    u""" Logging handler that write logs to SQLite DB.

    This logging handler supports an optional `record.siteconfig`
    attribute, to log which `siteconfig` produced the loggin message.

    Usage::

        logger = logging.getLogger(__name__)
        # logger.setLevel(logging.DEBUG)
        logger.addHandler(SQLiteHandler('log.sqlite'))
        logger.debug('…')

    :param filename: The SQLite database used for logging. the table
        will have the name ``log``.
    :type filename: str, unicode or None.

    :param store_only: a set to string if you want to store only log
        messages that have one of these ``extra`` attributes set.
        Default: store all log messages.
    :type: iterable of strings / unicode, or None.

    """

    def __init__(self, filename=None, store_only=None,
                 clear_first=False):
        """ Yo pep257, I love you. """

        logging.Handler.__init__(self)

        self.filename = filename or SQLITE_LOG_PATH
        self.store_only = store_only

        if clear_first:
            try:
                os.unlink(self.filename)
            except:
                pass

        self.db = sqlite3.connect(self.filename)

        self.db.execute(
            """CREATE TABLE IF NOT EXISTS log(
                id integer PRIMARY KEY autoincrement,
                date_created integer(4) NOT NULL default (strftime('%s','now')),

                log_level int,
                log_level_name text,

                name text,
                message text,
                args text,

                module text,
                func_name text,
                line_no int,
                filename text,

                exception text,
                process int,
                thread text,
                thread_name text,

                siteconfig text default null
            );
            """
        )
        self.db.commit()
        self.db.close()

    def emit(self, record):
        """ Handle the logging call. """

        if bool(self.store_only):
            do_not_store = True
            for extra in self.store_only:
                if bool(getattr(record, extra, None)):
                    do_not_store = False
                    break

            if do_not_store:
                return

        self.db = sqlite3.connect(self.filename)

        self.db.execute(
            """
                INSERT INTO log(
                    log_level,
                    log_level_name,

                    name,
                    message,
                    args,

                    module,
                    func_name,
                    line_no,
                    filename,

                    exception,
                    process,
                    thread,
                    thread_name,

                    siteconfig
                )
                VALUES(
                    ?,?,
                    ?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,
                    ?
                );""",
            (
                record.levelno,
                record.levelname,

                record.name,
                record.msg,
                json.dumps(record.args, cls=OrderedEncoder),

                record.module,
                record.funcName,
                record.lineno,
                os.path.abspath(record.filename),

                record.exc_text,
                record.process,
                record.thread,
                record.threadName,

                getattr(record, 'siteconfig', None),
            )
        )
        self.db.commit()
        self.db.close()


@app.template_filter('messageformat')
def messageformat(log):
    args = log['args']

    if args is None:
        return log['message']

    args = tuple(u','.join(x) if isinstance(x, list) else x
                 for x in json.loads(args))

    # LOGGER.info(args)

    # HEADS UP: without the tuple(), we get "not enough arguments…"
    #           even if args is a list. Go figure.
    return log['message'] % tuple(args)


@app.template_filter('siteconfig_test_url')
def siteconfig_test_url(log):
    args = log['args']

    if args is None:
        return None

    args = json.loads(args)

    for arg in args:
        if arg.startswith(u'http'):
            return arg

    return None


@app.template_filter('unixtimeformat')
def unixtimeformat(value, format='%H:%M / %d-%m-%Y'):

    return time.strftime(format, time.gmtime(value))


@app.template_filter('unixnaturaldelta')
def unixnaturaldelta(value):

    return naturaldelta(datetime.fromtimestamp(value))


@app.route('/')
@app.route('/index')
def index():
    """ Base testsuite view. """

    # setup_env()

    logs = Table('log', metadata, autoload=True)

    criticals = logs.select().where(logs.c.log_level == 50).order_by(
        'siteconfig', 'date_created')
    criticals_count = logs.count(logs.c.log_level == 50)

    errors = logs.select().where(logs.c.log_level == 40).order_by(
        'siteconfig', 'date_created')
    errors_count = logs.count(logs.c.log_level == 40)

    warnings = logs.select().where(logs.c.log_level == 30).order_by(
        'siteconfig', 'date_created')
    warnings_count = logs.count(logs.c.log_level == 30)

    infos = logs.select().where(logs.c.log_level == 20).order_by(
        'siteconfig', 'date_created')
    infos_count = logs.count(logs.c.log_level == 20)

    return render_template(
        'index.html',
        log_criticals=criticals.execute(),
        log_criticals_count=criticals_count.execute().first()[0],
        log_errors=errors.execute(),
        log_errors_count=errors_count.execute().first()[0],
        log_warnings=warnings.execute(),
        log_warnings_count=warnings_count.execute().first()[0],
        log_infos=infos.execute(),
        log_infos_count=infos_count.execute().first()[0],
    )

if __name__ == '__main__':
    app.run(debug=True)

    #    logger = logging.getLogger(__name__)
    #
    #    # Test the module.
    #    logger.setLevel(logging.DEBUG)
    #    logger.addHandler(SQLiteHandler('log.sqlite'))
    #    logger.debug('debug log message test.')
    #    logger.warning('warning log message test.')
    #    logger.error('error log message test.')
