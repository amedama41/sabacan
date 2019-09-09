"""This module provides sabacan command main function.
"""
import argparse
import sabacan.plantuml
import sabacan.redpen


__version__ = '0.0.1'


class SabacanParser(argparse.ArgumentParser):
    """Custom argparse.ArgumentParser which contains server URL and timeout.
    """
    server_url = None
    server_timeout = None


class SabacanCommonOptionAction(argparse.Action):
    """Custom argparse.Action which set SabacanParser attributes.
    """
    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(SabacanParser, self.dest, values)
        setattr(namespace, self.dest, values)


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
        action=SabacanCommonOptionAction,
        dest='server_url')
    parser.add_argument(
        '--timeout', '-t',
        help='server communication timeout (sec)',
        metavar='N',
        type=int,
        action=SabacanCommonOptionAction,
        dest='server_timeout')

    subparsers = parser.add_subparsers(
        title='supported subcommand',
        help='%(choices)s',
        metavar='subcommand',
        parser_class=SabacanParser)
    sabacan.plantuml.make_parser(subparsers.add_parser)
    sabacan.redpen.make_parser(subparsers.add_parser)

    args = parser.parse_args()
    args.main_function(args)
