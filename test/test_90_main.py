'''
    command_line test script
'''

import unittest
import test.context  # pylint: disable=unused-import
import mock
import puppetctl.command_line
from puppetctl import PuppetctlCLIHandler


class TestCommandLine(unittest.TestCase):
    ''' Class of tests about invoking the whole script. '''

    @staticmethod
    def test_main():
        ''' Test the main function entry '''
        with mock.patch.object(PuppetctlCLIHandler, 'main') as mock_main:
            puppetctl.command_line.main()
        mock_main.assert_called_once()
