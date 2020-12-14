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
        action='store',
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
        'input_files',
        help='Input document',
        nargs='*',
        metavar='<INPUT FILE>')
    parser.set_defaults(main_function=main)
    return parser


def get_default_configfile(lang):
    """Get default RedPen XML configuration file.

    Search current directory.
    If no configurations are found, search the parent directories
    until root directory.
    If no configurations are found, search $REDPEN_HOME/conf/.

    Args:
        lang: The languange which searched configuration file name includes.
    Returns:
        pathlib.Path:
            The path to configuration file. If not found, return None.
    """
    redpen_conf_lang_name = 'redpen-conf-' + lang + '.xml'
    def search_conf(dirpath):
        conf = dirpath / 'redpen-conf.xml'
        if conf.is_file():
            return conf
        conf = dirpath / redpen_conf_lang_name
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


def get_version(base_url, timeout=None, user_agent=None, ssl_context=None):
    """Get RedPen version.

    Args:
        base_url (str): URL of RedPen server.
        timeout (int): The server communication timeout in seconds.
        ssl_context (ssl.SSLContext): SSL Context for server communication.
    Returns:
        str: RedPen version.
    """
    url = base_url + '/rest/config/redpens'
    headers = sabacan.utils.make_headers(user_agent)
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(
            request, timeout=timeout, context=ssl_context) as response:
        result = json.loads(response.read().decode('utf8'))
        return result['version']


def get_language(base_url, document, timeout=None, ssl_context=None):
    """Get language of the document.

    Args:
        base_url (str): URL of RedPen server.
        document (str): Document to get which language uses.
        timeout (int): The server communication timeout in seconds.
        ssl_context (ssl.SSLContext): SSL Context for server communication.
    Returns:
        str: The language of the document.
    """
    url = base_url + '/rest/document/language'
    data = {'document': document}
    data = urllib.parse.urlencode(data).encode('utf8')
    headers = sabacan.utils.make_headers(user_agent)
    request = urllib.request.Request(url, data, headers)
    with urllib.request.urlopen(
            request, timeout=timeout, context=ssl_context) as response:
        result = json.loads(response.read().decode('utf8'))
        return result['key']


def validate(base_url, document, document_parser, lang, output_format,
             config=None, timeout=None, user_agent=None, ssl_context=None):
    """Validate document.

    Args:
        base_url (str): URL of RedPen server.
        document (str): Document to be validated.
        document_parser (str): Document format.
        lang (str): The language of document.
        output_format (str): The format of the validation result.
        config (str): The RedPen XML configuration.
        timeout (int): The server communication timeout in seconds.
        ssl_context (ssl.SSLContext): SSL Context for server communication.
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
    headers = sabacan.utils.make_headers(user_agent)
    request = urllib.request.Request(url, data, headers)
    with urllib.request.urlopen(
            request, timeout=timeout, context=ssl_context) as response:
        result = response.read().decode('utf8')
        if output_format.startswith('json'):
            return '[%s]' % result
        return result


def _exit_by_error(msg, *args, **kwargs):
    logging.error(msg, *args, **kwargs)
    sys.exit(1)


def _get_config(args):
    logging.debug('Getting configuration file...')
    if args.conf is None:
        return None
    config_file = pathlib.Path(args.conf)
    if not config_file.is_file():
        _exit_by_error('%s is not file', config_file)
    return config_file.read_text(encoding='utf8')

def _get_lang_from_config(config):
    logging.debug('Getting language from configuration file...')
    root = ET.fromstring(config)
    lang = root.attrib.get('lang', 'en')
    return lang

def _get_document_parser(args, document):
    if args.document_parser is not None:
        return args.document_parser
    if document.filename is not None:
        parser = get_document_parser_from_filename(document.filename)
        if parser is not None:
            return parser
    return 'plain'

def _get_default_config(lang, config_cache):
    if lang in config_cache:
        return config_cache[lang]
    logging.debug('Getting %s configuration file...', lang)
    config_file = get_default_configfile(lang)
    if config_file is None:
        logging.debug('Not found %s configuration file...', lang)
        config = None
    else:
        logging.debug('Found configuration file: %s', config_file)
        config = config_file.read_text(encoding='utf8')
    config_cache[lang] = config
    return config


class _Document:
    def __init__(self, document):
        self._is_file = isinstance(document, pathlib.Path)
        self._document = document

    @property
    def filename(self):
        """Get filename"""
        if self._is_file:
            return self._document.name
        return None

    @property
    def document(self):
        """Get document"""
        if self._is_file:
            return self._document.read_text(encoding='utf8')
        return self._document

def _get_documents(args):
    logging.debug('Getting documents...')
    if args.document is not None:
        return [_Document(args.document)]
    if not args.input_files:
        _exit_by_error('Input is not given')
    docs = []
    for input_file in args.input_files:
        path = pathlib.Path(input_file)
        if not path.is_file():
            _exit_by_error('Input is not regular file')
        docs.append(_Document(path))
    return docs

class _PlainMerger:
    def __init__(self):
        self._result = []

    def __call__(self, name, result):
        lines = result.splitlines()
        if name is not None:
            self._result.extend(name + ':' + line for line in lines)
        else:
            self._result.extend(lines)

    def __str__(self):
        return '\n'.join(self._result)

class _Plain2Merger:
    def __init__(self):
        self._result = ''

    def __call__(self, name, result):
        if name is not None:
            self._result += 'Document: ' + name + '\n'
        self._result += result

    def __str__(self):
        return self._result

class _JSONMerger:
    def __init__(self):
        self._result = []

    def __call__(self, name, result):
        json_result = json.loads(result)
        if name is not None:
            json_result[0]['document'] = name
        self._result.append(json_result[0])

    def __str__(self):
        return json.dumps(self._result, ensure_ascii=False)

class _XMLMerger:
    def __init__(self):
        self._result = ET.Element('validation-result')

    def __call__(self, name, result):
        root = ET.fromstring(result)
        for error in root.iterfind('error'):
            if name is not None:
                file_elem = ET.Element('file')
                file_elem.text = name
                idx = len(error)
                for idx, elem in enumerate(error):
                    if elem.tag == 'lineNum':
                        break
                error.insert(idx, file_elem)
            self._result.append(error)

    def __str__(self):
        return ET.tostring(self._result, encoding='utf8').decode('utf8')

def _merge_result(results, output_format):
    merger_map = {
        'plain': _PlainMerger,
        'plain2': _Plain2Merger,
        'json': _JSONMerger,
        'json2': _JSONMerger,
        'xml': _XMLMerger,
    }
    merger = merger_map[output_format]()
    for name, result in results:
        merger(name, result)
    return str(merger)


def main(args):
    """Run action as redpen command.

    Args:
        args: Parsing result from the parser created by `make_parser`.
    """
    base_url, options = sabacan.utils.get_connection_info(
        'redpen', default_url=_DEFAULT_SERVER_URL)

    if args.version:
        logging.debug('Getting RedPen version...')
        print(get_version(base_url, **options))
        sys.exit(0)

    global_config = _get_config(args)
    if global_config is not None:
        lang = _get_lang_from_config(global_config)
    config_cache = {}
    results = []
    num_error = 0
    for doc in _get_documents(args):
        logging.debug('Getting document parser...')
        document_parser = _get_document_parser(args, doc)
        contents = doc.document
        if global_config is None:
            if args.lang is None:
                logging.debug('Getting language from input document...')
                lang = get_language(base_url, contents, **options)
            else:
                lang = args.lang
            config = _get_default_config(lang, config_cache)
        else:
            config = global_config

        logging.debug('Validating input document '
                      '(document_parser=%s, lang=%s, format=%s)...',
                      document_parser, lang, args.format)
        try:
            result = validate(base_url,
                              contents, document_parser, lang, args.format,
                              config=config, **options)
        except urllib.error.HTTPError as error:
            with error:
                _exit_by_error('Failed to validate input document (%d %s): %s',
                               error.code, error.reason, error.read())
        results.append((doc.filename, result))

        logging.debug('Calculating the number of errors...')
        num_error += get_number_of_errors(result, args.format)

    print(_merge_result(results, args.format))
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
