#!/usr/bin/env python3
"""This module provides functions to access RedPen server.

This module may use the following environment variables.

:SABACAN_REDPEN_URL:
    URL of RedPen server. If SABACAN_REDPEN_URL does not exist,
    use SABACAN_URL instead.
:SABACAN_REDPEN_TIMEOUT:
    Timeout (sec) of RedPen server communication. If SABACAN_REDPEN_TIMEOUT
    does not exist, use SABACAN_TIMEOUT instead.
"""
import argparse
import json
import logging
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

import sabacan.utils
from sabacan.utils import NotSupportedAction


_SERVER_HOST = '127.0.0.1'
_SERVER_PORT = 8080
_DEFAULT_SERVER_URL = 'http://%s:%d' % (_SERVER_HOST, _SERVER_PORT)
_PARSER_EXTENSIONS_LIST = [
        ('markdown', ['md', 'markdown']),
        ('plain', ['txt']),
        ('wiki', ['wiki']),
        ('asciidoc', ['adoc', 'asciidoc']),
        ('latex', ['tex', 'latex']),
        ('rest', ['rest', 'rst']),
        ('review', ['re', 'review']),
        ('properties', ['properties']),
]
_FORMAT_LIST = ['json', 'json2', 'plain', 'plain2', 'xml']


def make_parser(parser_constructor=argparse.ArgumentParser):
    """Make argparse parser object for RedPen server.
    """
    parser = parser_constructor(
        'redpen',
        usage='%(prog)s [Options] [<INPUT FILE>]',
        description='CLI for RedPen server',
        add_help=False)
    parser.add_argument(
        '--conf', '-c',
        help='Configuration file',
        action='store',
        metavar='<CONF FILE>')
    parser.add_argument(
        '--format', '-f',
        help='Input file format (%(choices)s)',
        action='store',
        choices=[e[0] for e in _PARSER_EXTENSIONS_LIST],
        metavar='<FORMAT>',
        dest='document_parser')
    parser.add_argument(
        '--help', '-h',
        help='Displays this help information and exits',
        action='help')
    parser.add_argument(
        '--limit', '-l',
        help='Error limit number (default: %(default)d)',
        action='store',
        type=int,
        metavar='<LIMIT NUMBER>',
        default=1)
    parser.add_argument(
        '--lang', '-L',
        help='Language of error messages (%(choices)s)',
        action=NotSupportedAction,
        choices=['en', 'ja'],
        metavar='<LANGUAGE>')
    parser.add_argument(
        '--result-format', '-r',
        help='Output result format (%(choices)s) (default: %(default)s)',
        action='store',
        choices=_FORMAT_LIST,
        metavar='<RESULT FORMAT>',
        dest='format',
        default='plain')
    parser.add_argument(
        '--sentence', '-s',
        help='Input sentences',
        action='store',
        metavar='<INPUT SENTENCES>',
        dest='document')
    parser.add_argument(
        '--threshold', '-t',
        help='Threshold of error level (info, warn, error)',
        action=NotSupportedAction,
        choices=['info', 'warn', 'error'],
        metavar='<THRESHOLD>')
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Displays version information and exits')
    parser.add_argument(
        'input_file',
        help='Input document',
        nargs='?',
        metavar='<INPUT FILE>')
    parser.set_defaults(main_function=main)
    return parser


def get_default_configfile():
    """Get default RedPen XML configuration file.

    Search current directory.
    If no configurations are found, search the parent directories
    until root directory.
    If no configurations are found, search $REDPEN_HOME/conf/.

    Returns:
        pathlib.Path:
            The path to configuration file. If not found, return None.
    """
    def search_conf(dirpath):
        conf = dirpath / 'redpen-conf.xml'
        if conf.is_file():
            return conf
        for conf in dirpath.glob('redpen-conf-*.xml'):
            if conf.is_file():
                return conf
        return None

    current = pathlib.Path('.')
    conf = search_conf(current)
    if conf is not None:
        return conf
    for dirpath in current.resolve().parents:
        conf = search_conf(dirpath)
        if conf is not None:
            return conf
    redpen_home = pathlib.Path(os.getenv('REDPEN_HOME', '.'))
    return search_conf(redpen_home / 'conf')


def get_document_parser_from_filename(filename):
    """Get document format from the file extension.

    Args:
        filename: The filename of document.
    Returns:
        str: The format of the document.
    """
    suffix = pathlib.Path(filename).suffix
    if not suffix:
        return None
    for parser, extensions in _PARSER_EXTENSIONS_LIST:
        if suffix[1:] in extensions:
            return parser
    return None


def get_number_of_errors(result, output_format):
    """Get the number of errors in validation result.

    Args:
        result (str): A validation result.
        output_format (str): The format of the validation result.
    Returns:
        int: The number of errors in the validation result.
    """
    if output_format == 'json':
        result = json.loads(result)
        return len(result[0]['errors'])
    if output_format == 'json2':
        result = json.loads(result)
        return sum((len(error['errors']) for error in result[0]['errors']))
    if output_format == 'plain':
        return len(result.splitlines())
    if output_format == 'plain2':
        errors = re.finditer(r'^\s+(?!(Line|Sentence):)(?=\w)',
                             result, flags=re.MULTILINE)
        return sum((1 for _ in errors))
    if output_format == 'xml':
        root = ET.fromstring(result)
        return len(root.findall('error'))
    return 0 # Unknown format


def get_version(base_url, timeout=None):
    """Get RedPen version.

    Args:
        base_url (str): URL of RedPen server.
        timeout (int): The server communication timeout in seconds.
    Returns:
        str: RedPen version.
    """
    url = base_url + '/rest/config/redpens'
    with urllib.request.urlopen(url, timeout=timeout) as response:
        result = json.loads(response.read().decode('utf8'))
        return result['version']


def get_langauge(base_url, document, timeout=None):
    """Get language of the document.

    Args:
        base_url (str): URL of RedPen server.
        document (str): Document to get which language uses.
        timeout (int): The server communication timeout in seconds.
    Returns:
        str: The language of the document.
    """
    url = base_url + '/rest/document/language'
    data = {'document': document}
    data = urllib.parse.urlencode(data).encode('utf8')
    with urllib.request.urlopen(url, data, timeout=timeout) as response:
        result = json.loads(response.read().decode('utf8'))
        return result['key']


def validate(base_url, document, document_parser, lang, output_format,
             config=None, timeout=None):
    """Validate document.

    Args:
        base_url (str): URL of RedPen server.
        document (str): Document to be validated.
        document_parser (str): Document format.
        lang (str): The language of document.
        output_format (str): The format of the validation result.
        config (str): The RedPen XML configuration.
        timeout (int): The server communication timeout in seconds.
    Returns:
        str: The validation result with the specified format.
    """
    # pylint: disable=too-many-arguments
    data = {
        'document': document,
        'documentParser': document_parser,
        'lang': lang,
        'format': output_format,
    }
    if config is not None:
        data['config'] = config

    url = base_url + '/rest/document/validate'
    data = urllib.parse.urlencode(data).encode('utf8')
    with urllib.request.urlopen(url, data, timeout=timeout) as response:
        result = response.read().decode('utf8')
        if output_format.startswith('json'):
            return '[%s]' % result
        return result


def _exit_by_error(msg, *args, **kwargs):
    logging.error(msg, *args, **kwargs)
    sys.exit(1)


def _get_config(args):
    if args.conf is None:
        config_file = get_default_configfile()
    else:
        config_file = pathlib.Path(args.conf)
    if config_file is None:
        return None
    if not config_file.is_file():
        _exit_by_error('%s is not file', config_file)
    return config_file.read_text()


def _get_document_parser(args):
    if args.document_parser is not None:
        return args.document_parser
    if args.input_file is not None:
        parser = get_document_parser_from_filename(args.input_file)
        if parser is not None:
            return parser
    return 'plain'


def _get_document(args):
    if args.document is not None:
        return args.document
    if args.input_file is None:
        _exit_by_error('Input is not given')
    input_file = pathlib.Path(args.input_file)
    if not input_file.is_file():
        _exit_by_error('Input is not regular file')
    return input_file.read_text()


def main(args):
    """Run action as redpen command.

    Args:
        args: Parsing result from the parser created by `make_parser`.
    """
    base_url = sabacan.utils.get_server_url('redpen', _DEFAULT_SERVER_URL)
    timeout = sabacan.utils.get_timeout('redpen')

    if args.version:
        logging.debug('Getting RedPen version...')
        print(get_version(base_url, timeout=timeout))
        sys.exit(0)

    logging.debug('Getting configuration file...')
    config = _get_config(args)
    logging.debug('Getting document...')
    document = _get_document(args)
    logging.debug('Getting document parser...')
    document_parser = _get_document_parser(args)
    if config is not None:
        logging.debug('Getting language from configuration file...')
        root = ET.fromstring(config)
        lang = root.attrib.get('lang', 'en')
    else:
        logging.debug('Getting language from input document...')
        lang = get_langauge(base_url, document, timeout=timeout)

    logging.debug('Validating input document '
                  '(document_parser=%s, lang=%s, format=%s)...',
                  document_parser, lang, args.format)
    try:
        result = validate(base_url,
                          document, document_parser, lang, args.format,
                          config=config, timeout=timeout)
    except urllib.error.HTTPError as error:
        with error:
            _exit_by_error('Failed to validate input document (%d %s): %s',
                           error.code, error.reason, error.read())
    print(result)

    logging.debug('Calculating the number of errors...')
    num_error = get_number_of_errors(result, args.format)
    logging.debug('The number of errors is %d', num_error)
    if args.limit < num_error:
        _exit_by_error('The number of errors "%d" is larger'
                       ' than specified (limit is "%d")',
                       num_error, args.limit)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.debug('Parsing command line options...')
    ARGS = make_parser().parse_args()
    ARGS.main_function(ARGS)
