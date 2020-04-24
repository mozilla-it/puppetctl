'''
    PuppetctlExecution.panic_stop test script
'''

import unittest
import sys
import os
import signal
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlExecution
if sys.version_info.major >= 3:
    from io import StringIO  # pragma: no cover
else:
    from io import BytesIO as StringIO  # pragma: no cover


class TestExecutionPanicStop(unittest.TestCase):
    ''' Class of tests about executing puppetctl panic_stop commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-panic_stop-statefile-mods.test.txt'
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = 'testingpuppetctl[{}]'.format(self.library.invoking_user)

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:  # pragma: no cover
            # we likely never created the file.
            pass

    def test_perms_block_panic_stop(self):
        ''' Test that non-root can't run the important functions. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=False):
            with self.assertRaises(SystemExit) as fail_break, \
                    mock.patch('sys.stdout', new=StringIO()):
                oneoff.panic_stop(True)
            self.assertEqual(fail_break.exception.code, 2)

    def test_panic_stop_nothing_to_do(self):
        ''' Test that 'panic_stop' handles no-processes-to-kill nicely. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  return_value={}), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(False)
        self.assertIn("No running 'puppet agent' found", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 0)

    def test_panic_stop_well_behaved(self):
        ''' Test that 'panic_stop' leaves quietly if a process exits cleanly. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'123': 'test-puppet agent'}, {}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(False)
        mock_kill.assert_called_once_with('123', signal.SIGTERM)
        mock_sleep.assert_called_once_with(2)
        self.assertIn("Sending SIGTERM to pid 123 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("No running 'puppet agent' found", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 0)

        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'234': 'test-puppet agent'}, {}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(True)
        mock_kill.assert_called_once_with('234', signal.SIGTERM)
        mock_sleep.assert_not_called()
        self.assertIn("Sending SIGTERM to pid 234 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("No running 'puppet agent' found", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 0)

    def test_panic_stop_stubborn(self):
        ''' Test that 'panic_stop' fires a kill if term wasn't enough. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'123': 'test-puppet agent'},
                                               {'123': 'test-puppet agent'}, {}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(False)
        mock_kill.assert_any_call('123', signal.SIGTERM)
        mock_sleep.assert_any_call(2)  # the non-force pause
        mock_kill.assert_called_with('123', signal.SIGKILL)
        mock_sleep.assert_any_call(1)  # the mandatory pause after the kill signal
        self.assertIn("Sending SIGTERM to pid 123 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("Sending SIGKILL to pid 123 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("No running 'puppet agent' found", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 0)

        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'234': 'test-puppet agent'},
                                               {'234': 'test-puppet agent'}, {}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(True)
        mock_kill.assert_any_call('234', signal.SIGTERM)
        mock_kill.assert_called_with('234', signal.SIGKILL)
        mock_sleep.assert_any_call(1)  # the mandatory pause after the kill signal
        self.assertIn("Sending SIGTERM to pid 234 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("Sending SIGKILL to pid 234 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("No running 'puppet agent' found", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 0)

    def test_panic_stop_zombies(self):
        ''' Test that 'panic_stop' complains if a process outlives a sigkill. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'123': 'test-puppet agent'},
                                               {'123': 'test-puppet agent'},
                                               {'123': 'test-puppet agent'}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(False)
        mock_kill.assert_any_call('123', signal.SIGTERM)
        mock_sleep.assert_any_call(2)  # the non-force pause
        mock_kill.assert_called_with('123', signal.SIGKILL)
        mock_sleep.assert_any_call(1)  # the mandatory pause after the kill signal
        self.assertIn("Sending SIGTERM to pid 123 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("Sending SIGKILL to pid 123 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("pid 123 / 'test-puppet agent' did NOT die", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 1)

        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                  side_effect=[{'234': 'test-puppet agent'},
                                               {'234': 'test-puppet agent'},
                                               {'234': 'test-puppet agent'}]), \
                self.assertRaises(SystemExit) as exit_panicstop, \
                mock.patch('os.kill') as mock_kill, \
                mock.patch('time.sleep') as mock_sleep, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.panic_stop(True)
        mock_kill.assert_any_call('234', signal.SIGTERM)
        mock_kill.assert_called_with('234', signal.SIGKILL)
        mock_sleep.assert_any_call(1)  # the mandatory pause after the kill signal
        self.assertIn("Sending SIGTERM to pid 234 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("Sending SIGKILL to pid 234 / 'test-puppet agent'", fake_out.getvalue())
        self.assertIn("pid 234 / 'test-puppet agent' did NOT die", fake_out.getvalue())
        self.assertEqual(exit_panicstop.exception.code, 1)
