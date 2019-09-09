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
from sabacan.utils import SetEnvAction


__version__ = '0.0.1'


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

    subparsers = parser.add_subparsers(
        title='supported subcommand',
        help='%(choices)s',
        metavar='subcommand')
    sabacan.plantuml.make_parser(subparsers.add_parser)
    sabacan.redpen.make_parser(subparsers.add_parser)

    args = parser.parse_args()
    args.main_function(args)
