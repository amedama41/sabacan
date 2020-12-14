"""This module provides sabacan command main function.

This module may use the following environment variables.

:SABACAN_URL:
    URL of server.
:SABACAN_TIMEOUT:
    Timeout (sec) of server communication.
"""
import argparse
import sabacan.plantuml
import sabacan.redpen
from sabacan.utils import SetEnvAction, SetFlagEnvAction


__version__ = '0.0.4'


def main():
    """Run sabacan command.
    """
    parser = argparse.ArgumentParser('sabacan')
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='%%(prog)s %s' % __version__)
    parser.add_argument(
        '--url', '-u',
        help='server URL',
        metavar='URL',
        action=SetEnvAction,
        dest='SABACAN_URL')
    parser.add_argument(
        '--timeout', '-t',
        help='server communication timeout (sec)',
        metavar='N',
        type=int,
        action=SetEnvAction,
        dest='SABACAN_TIMEOUT')
    parser.add_argument(
        '--user-agent',
        help='User-Agent for server communication',
        metavar='UserAgent',
        action=SetEnvAction,
        dest='SABACAN_USER_AGENT')
    parser.add_argument(
        '--insecure',
        help='Allow connections to SSL sites without certs',
        action=SetFlagEnvAction,
        dest='_SABACAN_INSECURE',
        default='0')

    subparsers = parser.add_subparsers(
        title='supported subcommand',
        help='%(choices)s',
        metavar='subcommand')
    sabacan.plantuml.make_parser(subparsers.add_parser)
    sabacan.redpen.make_parser(subparsers.add_parser)

    args = parser.parse_args()
    if hasattr(args, 'main_function'):
        args.main_function(args)
    else:
        parser.print_help()
