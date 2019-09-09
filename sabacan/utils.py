"""This module provides utility function to sabacan.
"""
import argparse
import logging
import os


class SetEnvAction(argparse.Action): # pylint: disable=too-few-public-methods
    """Custom argparse.Action which set environment variable.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        os.environ[self.dest] = values

def get_server_url(servername, default=None):
    """Get URL for server from environment variables.

    Args:
        servername (str): The name of application (e.g. plantuml)
        default (str): The result when URL done not exist
            in environment variables.
    Returns:
        str: URL of server
    """
    url = os.getenv('SABACAN_%s_URL' % servername.upper())
    if url is not None:
        return url
    return os.getenv('SABACAN_URL', default)

def get_timeout(servername, default=None):
    """Get timeout for server communication from environment variables.

    Args:
        servername (str): The name of application (e.g. plantuml)
        default (int): The result when timeout does not exist
            in environment variables.
    Returns:
        str: The timeout (sec) of server communication.
    """
    timeout = os.getenv('SABACAN_%s_TIMEOUT' % servername.upper())
    if timeout is None:
        timeout = os.getenv('SABACAN_TIMEOUT', default)
    if timeout is not None:
        try:
            return int(timeout)
        except ValueError:
            pass
    return None


class NotSupportedAction(argparse.Action):
    """Custom argparse.Action class for not supported options.

    The help message for an option attached to this class is appended
    'NOT SUPPORTED' to.
    When the options are used, waning messages are displayed automatically.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        # pylint: disable=too-many-arguments,redefined-builtin
        help = 'NOT SUPPORTED' if help is None else help + ' (NOT SUPPORTED)'
        super(NotSupportedAction, self).__init__(
            option_strings, dest, nargs, const,
            default, type, choices, required, help, metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        logging.warning('"%s" is not supported', option_string)


class NotSupportedFlagAction(NotSupportedAction):
    """Custom argparse.Action class for not supported options.

    The class is same as NotSupportedAction except nargs is always 0.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        # pylint: disable=too-many-arguments,redefined-builtin
        super(NotSupportedFlagAction, self).__init__(
            option_strings, dest, 0, const,
            default, type, choices, required, help, metavar)
