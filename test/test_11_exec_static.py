'''
    PuppetctlExecution static method tester
'''

import unittest
import sys
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlExecution
if sys.version_info.major >= 3:
    from io import StringIO  # pragma: no cover
else:
    from io import BytesIO as StringIO  # pragma: no cover


class TestExecutionStatics(unittest.TestCase):
    ''' Class of tests about PuppetctlExecution's static method. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.library = PuppetctlExecution('/tmp/does-not-matter.status.txt')

    def test_dhms(self):
        ''' Test the dhms function for various times '''
        self.assertEqual(self.library.dhms(0), '0s')
        self.assertEqual(self.library.dhms(30), '30s')
        self.assertEqual(self.library.dhms(60), '1m')
        self.assertEqual(self.library.dhms(90), '1m 30s')
        self.assertEqual(self.library.dhms(60*60), '1h')
        self.assertEqual(self.library.dhms(61*60), '1h 1m')
        self.assertEqual(self.library.dhms(61*60+20), '1h 1m 20s')
        self.assertEqual(self.library.dhms(11*60*60), '11h')
        self.assertEqual(self.library.dhms(24*60*60), '1d')

    def test_log(self):
        ''' test the syslog call of log '''
        with mock.patch('syslog.openlog') as mock_openlog, \
                mock.patch('syslog.syslog') as mock_syslog:
            self.library.syslog = mock_syslog
            self.library.log('foo bar baz')
            mock_openlog.assert_called_once_with(self.library.logging_tag)
            mock_syslog.assert_called_once_with('foo bar baz')

    def test_log_print_to_log(self):
        ''' test that log_print calls what it should '''
        with mock.patch.object(PuppetctlExecution, 'log') as mock_log, \
                mock.patch.object(PuppetctlExecution, 'color_print') as mock_print:
            # we don't care what it prints, just that it tries to.
            with mock.patch('sys.stdout', new=StringIO()):
                self.library.log_print('foo', '1;31')
            mock_log.assert_called_once_with('foo')
            mock_print.assert_called_once_with('foo', '1;31')

    def test_color_print_notty(self):
        ''' test that color_print handles a notty '''
        # Order matters here: isatty comes second since we are touching stdout twice.
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch('sys.stdout.isatty', return_value=False):
            self.library.color_print('bar')
            self.assertEqual(fake_out.getvalue(), 'puppetctl: bar\n')

    def test_color_print_tty(self):
        ''' test that color_print handles a tty '''
        # Order matters here: isatty comes second since we are touching stdout twice.
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch('sys.stdout.isatty', return_value=True):
            self.library.color_print('baz')
            self.assertEqual(fake_out.getvalue(), 'baz\n')

    def test_color_print_tty_color(self):
        ''' test that color_print handles a tty with color '''
        # Order matters here: isatty comes second since we are touching stdout twice.
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch('sys.stdout.isatty', return_value=True):
            self.library.color_print('quux', '1;31')
            self.assertEqual(fake_out.getvalue(), '\033[1;31mquux\033[0m\n')

    def test_error_print(self):
        ''' Test if error_print works correctly '''
        # most of the testing here is actually done by log_print
        with self.assertRaises(SystemExit) as error_print, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.error_print('some test message')
        self.assertIn('some test message', fake_out.getvalue())
        self.assertEqual(error_print.exception.code, 2)
