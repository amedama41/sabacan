#!/usr/bin/env python3
"""This module provides functions to access PlantUML server.

This module may use the following environment variables.

:SABACAN_PLANTUML_URL:
    URL of RedPen server. If SABACAN_PLANTUML_URL does not exist,
    use SABACAN_URL instead.
:SABACAN_PLANTUML_TIMEOUT:
    Timeout (sec) of RedPen server communication. If SABACAN_PLANTUML_TIMEOUT
    does not exist, use SABACAN_TIMEOUT instead.
"""
import argparse
import base64
import glob
import io
import logging
import os
import pathlib
import sys
import urllib.error
import urllib.request
import zlib

import sabacan.utils
from sabacan.utils import NotSupportedAction, NotSupportedFlagAction

_FROM_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
_TO_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_?'
_ENCODE_TABLE = dict(zip(_FROM_CHARS, _TO_CHARS))
_DECODE_TABLE = dict(zip(_TO_CHARS, _FROM_CHARS))

_FORMAT_LIST = [
    'png', 'braille',
    'svg', 'svg:nornd',
    'eps', 'eps:text',
    'pdf', 'vdx',
    'xmi', 'xmi:argo', 'xmi:star',
    'scxml', 'html',
    'txt', 'utxt',
    'latex', 'latex:nopreamble'
    'base64',
]
_FORMAT_TO_URL_PATTERN_TABLE = {
    'eps:text': 'epstext',
    'utxt': 'txt',
}

DEFAULT_SERVER_URL = 'http://%s:%d/plantuml' % ('127.0.0.1', 8080)


class _FlagAction(argparse.Action):
    """Custom argparse.Action class to display variable information.

    This class compile dest as PlantUML code when the action is invoked.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        # pylint: disable=too-many-arguments,redefined-builtin
        super(_FlagAction, self).__init__(option_strings, dest, 0, const,
                                          default, type, choices, required,
                                          help, metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        base_url, options = sabacan.utils.get_connection_info(
            'plantuml', default_url=DEFAULT_SERVER_URL)
        code = '@startuml\n' + self.dest + '\n@enduml'
        try:
            result = compile_code(base_url, code, 'txt', **options)
            lines = result.decode('utf-8').splitlines()
            print('\n'.join(line.strip() for line in lines))
        except Exception as ex: # pylint: disable=broad-except
            logging.error('Failed to display %s: %s', self.dest, ex)
            parser.exit(1)
        parser.exit(0)


class _LanguageAction(argparse.Action):
    """Custom argparse.Action class to display PlantUML language information.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        # pylint: disable=too-many-arguments,redefined-builtin
        super(_LanguageAction, self).__init__(
            option_strings, dest, 0, const,
            default, type, choices, required, help, metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        base_url, options = sabacan.utils.get_connection_info(
            'plantuml', default_url=DEFAULT_SERVER_URL)
        try:
            print(get_language(base_url, **options))
        except Exception as ex: # pylint: disable=broad-except
            logging.error('Failed to display language: %s', ex)
            parser.exit(1)
        parser.exit(0)


def make_parser(parser_constructor=argparse.ArgumentParser):
    """Make argparse parser object for PlantUML server.
    """
    # pylint: disable=too-many-statements
    parser = parser_constructor(
        'plantuml',
        usage='%(prog)s [options] [file/dir] [file/dir] [file/dir]',
        description='CLI for PlantUML server',
        add_help=False)
    parser.add_argument(
        '-gui',
        help='To run the graphical user interface',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-t',
        help='To generate images using specified format (default is PNG)',
        action='store',
        choices=_FORMAT_LIST,
        default='png',
        metavar='format',
        dest='format')
    parser.add_argument(
        '-output', '-o',
        help='To generate images in the specified directory',
        action='store',
        metavar='"dir"',
        dest='outdir')
    parser.add_argument(
        '-ofile',
        help='To generate an image with the specified filename',
        action='store',
        metavar='"file"',
        dest='outfile')
    parser.add_argument(
        '-D',
        action='store',
        metavar='VAR1=value',
        help=('Not support currently. '
              'To set a preprocessing variable '
              'as if \'!define VAR1 value\' were used'))
    parser.add_argument(
        '-S',
        help=('Not support currently. '
              'To set a skin parameter '
              'as if \'skinparam param1 value\' were used'),
        action='store',
        metavar='param1=value')
    parser.add_argument(
        '-recurse', '-r',
        help='recurse through directories',
        action='store_true')
    parser.add_argument(
        '-config', '-c',
        help=('Not support currently. '
              'To read the provided config file before each diagram'),
        metavar='"file"',
        action='store')
    parser.add_argument(
        '-I',
        help=('Not support currently. '
              'To include file as if \'!include file\' were used'),
        action='store',
        metavar='/path/to/file')
    parser.add_argument(
        '-charset',
        help=('Not support currently. '
              'To use a specific charset (default is US-ASCII)'),
        action='store',
        metavar='xxx')
    parser.add_argument(
        '-exclude', '-x',
        help=('Not support currently. '
              'To exclude files that match the provided pattern'),
        action='store',
        metavar='pattern')
    parser.add_argument(
        '-metadata',
        help='To retrieve PlantUML sources from PNG images',
        action='store_true')
    parser.add_argument(
        '-nometadata',
        help='To NOT export metadata in PNG/SVG generated files',
        action='store_true')
    parser.add_argument(
        '-checkmetadata',
        help='Skip PNG files that don\'t need to be regenerated',
        action='store_true')
    parser.add_argument(
        '-logdata',
        help='TODO',
        action='store',
        metavar='"file"')
    parser.add_argument(
        '-word',
        help='TODO',
        action='store_true')
    parser.add_argument(
        '-version',
        help='To display information about PlantUML and Java versions',
        action=_FlagAction)
    parser.add_argument(
        '-license',
        help='To display license',
        action=_FlagAction)
    parser.add_argument(
        '-checkversion',
        help='To check if a newer version is available for download',
        action=_FlagAction)
    parser.add_argument(
        '-verbose', '-v',
        help='To have log information',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-quiet',
        help=('Not support currently. '
              'To NOT print error message into the console'),
        action='store_true')
    parser.add_argument(
        '-debugsvek', '-debug_svek',
        help='To generate intermediate svek files',
        action=NotSupportedFlagAction)
    # parser.add_argument(
    #     '-keepfiles',
    #     help='NOT delete temporary files after process.',
    #     action=NotSupportedFlagAction)
    parser.add_argument(
        '-help', '-h', '-?',
        help='To display this help message',
        action='help')
    parser.add_argument(
        '-testdot',
        help='To test the installation of graphviz',
        action=_FlagAction)
    parser.add_argument(
        '-graphvizdot', '-graphviz_dot',
        help='To specify dot executable',
        action=NotSupportedAction,
        metavar='"exe"')
    parser.add_argument(
        '-pipe', '-p',
        help=('To use stdin for PlantUML source '
              'and stdout for PNG/SVG/EPS generation'),
        action='store_true')
    parser.add_argument(
        '-encodesprite',
        help=('To encode a sprite at gray level (z for compression) '
              'from an image'),
        action=NotSupportedAction,
        choices=['4', '8', '16', '4z', '8z', '16z'])
    parser.add_argument(
        '-computeurl', '-encodeurl',
        help='To compute the encoded URL of a PlantUML source file',
        action='store_true')
    parser.add_argument(
        '-decodeurl',
        help='To retrieve the PlantUML source from an encoded URL',
        action='store_true')
    parser.add_argument(
        '-syntax',
        help=('To report any syntax error '
              'from standard input without generating images'),
        action='store_true')
    parser.add_argument(
        '-language',
        help='To print the list of PlantUML keywords',
        action=_LanguageAction)
    # parser.add_argument(
    #     '-nosuggestengine',
    #     action='store_true',
    #     help='To disable the suggest engine when errors in diagrams')
    parser.add_argument(
        '-checkonly',
        help='To check the syntax of files without generating images',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-failfast',
        help=('To stop processing '
              'as soon as a syntax error in diagram occurs'),
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-failfast2',
        help=('To do a first syntax check before processing files, '
              'to fail even faster'),
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-pattern',
        help='To print the list of Regular Expression used by PlantUML',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-duration',
        help='To print the duration of complete diagrams processing',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-nbthread',
        help='To use (N) threads for processing',
        action=NotSupportedAction,
        metavar='N')
    parser.add_argument(
        '-timeout',
        help=('Processing timeout in (N) seconds. '
              'Defaults to 15 minutes (900 seconds).'),
        action=NotSupportedAction,
        metavar='N')
    parser.add_argument(
        '-about', '-authors', '-author',
        help='To print information about PlantUML authors',
        action=_FlagAction,
        dest='authors')
    parser.add_argument(
        '-overwrite',
        help='To allow to overwrite read only files',
        action='store_true')
    parser.add_argument(
        '-printfonts',
        help='To print fonts available on your system',
        action=_FlagAction,
        dest='help font')
    parser.add_argument(
        '-enablestats',
        help='To enable statistics computation',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-disablestats',
        help='To disable statistics computation (default)',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-htmlstats',
        help='To output general statistics in file plantuml-stats.html',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-xmlstats',
        help='To output general statistics in file plantuml-stats.xml',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-realtimestats',
        help='To generate statistics on the fly rather than at the end',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-loopstats',
        help='To continuously print statistics about usage',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-dumpstats',
        help='TODO',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-dumphtmlstats',
        help='TODO',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-clipboard',
        help='TODO',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-clipboardloop',
        help='TODO',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-splash',
        help='To display a splash screen with some progress bar',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-progress',
        help='To display a textual progress bar in console',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-pipedelimitor',
        help='TODO',
        action='store')
    parser.add_argument(
        '-pipemap',
        help='Not support currently. TODO',
        action='store_true')
    parser.add_argument(
        '-pipenostderr',
        help='Not support currently. TODO',
        action='store_true')
    parser.add_argument(
        '-pipeimageindex',
        help=('Not support currently. '
              'To generate the Nth image with pipe option'),
        action='store',
        metavar='N')
    parser.add_argument(
        '-stdlib',
        help='To print standard library info',
        action=_FlagAction)
    parser.add_argument(
        '-extractstdlib',
        help='To extract PlantUML Standard Library into stdlib folder',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-stdrpt', '-stdrpt:1',
        help='Not support currently. TODO',
        action='store_true')
    parser.add_argument(
        '-useseparatorminus',
        help='Not support currently. TODO',
        action='store_true')
    parser.add_argument(
        '-filename',
        help='Not support currently. To override %%filename%% variable',
        action='store',
        metavar='"example.puml"')
    parser.add_argument(
        '-preproc',
        help='To output preprocessor text of diagrams',
        action=NotSupportedFlagAction)
    parser.add_argument(
        '-cypher',
        help='To cypher texts of diagrams so that you can share them',
        action=NotSupportedFlagAction)
    parser.add_argument(
        'file/dir',
        help='UML files',
        nargs='*')
    parser.set_defaults(main_function=main)
    return parser


class CompileError(RuntimeError):
    """Exception for compile error.
    """
    def __init__(self, msg, data):
        super(CompileError, self).__init__(msg)
        self.data = data


def encode_code(uml_code, level=-1):
    """Encode PlantUML code by PlantUML Text Encoding
    (http://plantuml.com/en/text-encoding).

    Args:
        uml_code (str): PlantUML code.
        level (int): Compressing level.
    Returns:
        str: The PlantUML Text Encoding text.
    """
    byte_code = uml_code.encode('utf-8')
    compressed_code = zlib.compress(byte_code, level)[2:-4]
    base64_code = base64.b64encode(compressed_code).decode('ascii')
    return ''.join(_ENCODE_TABLE[c] for c in base64_code)


def decode_code(encoded_uml):
    """Decode PlantUML Text Encoding text to PlantUML code.

    Args:
        encoded_uml (str): PlantUML Text Encoding text.
    Returns:
        str: PlantUML code.
    """
    base64_code = ''.join(_DECODE_TABLE[c] for c in encoded_uml)
    compressed_code = base64.b64decode(base64_code)
    wbits = 15 if compressed_code[0:2] == b'\x78\x9c' else -15
    byte_code = zlib.decompress(compressed_code, wbits)
    return byte_code.decode('utf-8')


def compile_code(base_url, uml_code, output_format, use_post=False,
                 timeout=None, user_agent=None, ssl_context=None):
    # pylint: disable=too-many-arguments
    """Compile PlantUML code into the specified format data by PlantUML server.

    Args:
        base_url (str): URL of PlantUML server.
        uml_code (str): PlantUML code.
        output_format (str): The target format.
        use_post (bool): Whether or not to use HTTP POST method for compiling.
            PlantUML server supports POST method from version 1.2018.5.
        timeout (int): The server communication timeout in seconds.
        ssl_context (ssl.SSLContext): SSL Context for server communication.
    Returns:
        bytes: output data with the specified format.
    Raises:
        CompileError: If PlantUML code can not be compiled.
        urllib.error.HTTPError: If some server error occurs.
        urllib.error.URLError: If some protocol error occurs.
    """
    headers = sabacan.utils.make_headers(user_agent)
    pattern = _FORMAT_TO_URL_PATTERN_TABLE.get(output_format, output_format)
    if use_post:
        url = base_url + '/' + pattern + '/'
        data = uml_code.encode('utf-8')
        headers['Content-Type'] = 'text/plain;charset="UTF-8"'
        request = urllib.request.Request(url, data, headers)
    else:
        encoded_uml = encode_code(uml_code)
        url = base_url + '/' + pattern + '/' + encoded_uml
        request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(
                request, timeout=timeout, context=ssl_context) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        with error:
            if error.code != 400:
                raise
            raise CompileError(error.reason, error.read())


def get_language(base_url, timeout=None, user_agent=None, ssl_context=None):
    """Get PlantUML languange information.

    Args:
        base_url (str): URL of PlantUML server.
        timeout (int): The server communication timeout in seconds.
        ssl_context (ssl.SSLContext): SSL Context for server communication.
    Returns:
        str: PlantUML language information.
    """
    url = base_url + '/language'
    headers = sabacan.utils.make_headers(user_agent)
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(
            request, timeout=timeout, context=ssl_context) as response:
        return response.read().decode('utf8')


def format_to_ext(output_format):
    """Get a file extension from the output format

    Args:
        output_format (str): The target format.
    Returns:
        str: The corresponding file extension with '.ext' format.
    """
    if output_format == 'txt':
        return '.atxt'
    if output_format == 'braille':
        return '.braille.png'
    index = output_format.find(':')
    if index != -1:
        return '.' + output_format[0:index]
    return '.' + output_format


def _generate(base_url, options,
              filepath, output_format, outdir, output_filepath=None):
    # pylint: disable=too-many-arguments
    uml_code = filepath.read_text(encoding='utf-8')
    try:
        reply = compile_code(base_url, uml_code, output_format, **options)
        result = True
    except CompileError as error:
        logging.warning('%s: %s', filepath, error)
        reply = error.data
        result = False

    if output_filepath is None:
        output_filepath = filepath.parent / outdir / filepath.name
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
    output_filepath = output_filepath.with_suffix(format_to_ext(output_format))
    output_filepath.write_bytes(reply)
    return result

def _check_syntax(base_url, options, filepath):
    uml_code = filepath.read_text(encoding='utf-8')
    try:
        reply = compile_code(
            base_url, uml_code, 'check', use_post=False, **options)
        result = True
    except CompileError as error:
        logging.warning('%s: %s', filepath, error)
        reply = error.data
        result = False
    print(filepath, ':', reply.decode('utf-8'))
    return result

def _encodeurl(filepath):
    try:
        uml_code = filepath.read_text(encoding='utf-8')
        print(filepath, ':', encode_code(uml_code))
    except Exception as ex: # pylint: disable=broad-except
        logging.error('Failed to encode %s: %s', uml_code, ex)
        return False
    return True

def _decodeurl(encoded_uml):
    try:
        print(decode_code(encoded_uml))
    except Exception as ex: # pylint: disable=broad-except
        logging.error('Failed to decode %s: %s', encoded_uml, ex)
        return False
    return True

def _for_each_file(paths, proc, do_exit=False):
    result = True
    for path in paths:
        path = os.path.expandvars(os.path.expanduser(path))
        do_process = False
        for filepath in glob.iglob(path, recursive=True):
            filepath = pathlib.Path(filepath)
            if not filepath.is_file():
                continue
            do_process = True
            try:
                result = proc(filepath) and result
            except Exception: # pylint: disable=broad-except
                logging.exception('%s: Failed to process', filepath)
                result = False
        if not do_process:
            logging.warning('%s is invalid path', path)
            continue
    if do_exit:
        sys.exit(0 if result else 1)
    return result

def _read_uml_code(stdin):
    code_lines = []
    for line in stdin:
        code_lines.append(line)
        if line.startswith('@end'):
            return '\n'.join(code_lines)
    return '\n'.join(code_lines)

def _run_with_pipe(base_url, options, args):
    result = True
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    while True:
        uml_code = _read_uml_code(stdin)
        if not uml_code:
            break
        try:
            if args.syntax:
                fmt = 'check'
                use_post = False
            else:
                fmt = args.format
                use_post = True
            reply = compile_code(base_url, uml_code, fmt,
                                 use_post=use_post, **options)
            sys.stdout.buffer.write(reply)
        except CompileError as error:
            logging.warning('%s', error)
            sys.stdout.buffer.write(error.data)
            result = False
        except Exception: # pylint: disable=broad-except
            logging.exception('Failed to compile')
            result = False
        if args.pipedelimitor is not None:
            print(args.pipedelimitor)
    sys.exit(0 if result else 1)


def main(args):
    """Run action as plantuml command.

    Args:
        args: Parsing result from the parser created by `make_parser`.
    """
    base_url, options = sabacan.utils.get_connection_info(
        'plantuml', default_url=DEFAULT_SERVER_URL)

    if args.pipe:
        _run_with_pipe(base_url, options, args)

    input_paths = getattr(args, 'file/dir')
    if args.computeurl:
        _for_each_file(input_paths, _encodeurl, do_exit=True)

    if args.decodeurl:
        result = all(_decodeurl(encoded_uml) for encoded_uml in input_paths)
        sys.exit(0 if result else 1)

    if args.syntax:
        _for_each_file(
            input_paths,
            lambda path: _check_syntax(base_url, options, path),
            do_exit=True)

    if args.outfile is not None:
        outfile = pathlib.Path(args.outfile)
        if not outfile.parent.exists(): # TODO argument value check
            logging.error('Invalid output filepath: %s', outfile)
            sys.exit(1)
    else:
        outfile = None
    if args.outdir is not None:
        outdir = pathlib.Path(args.outdir) # TODO argument value check
    else:
        outdir = ''

    _for_each_file(
        input_paths,
        lambda path: _generate(
            base_url, options, path, args.format, outdir, outfile),
        do_exit=True)


if __name__ == '__main__':
    ARGS = make_parser().parse_args()
    ARGS.main_function(ARGS)
