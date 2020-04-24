'''
    PuppetctlExecution.run test script
'''

import unittest
import sys
import os
import time
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile, PuppetctlExecution
if sys.version_info.major >= 3:
    from io import StringIO  # pragma: no cover
else:
    from io import BytesIO as StringIO  # pragma: no cover


class TestExecutionRun(unittest.TestCase):
    ''' Class of tests about executing puppetctl run commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-run-statefile-mods.test.txt'
        self.pe_patcher = mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                            return_value=True)
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = 'testingpuppetctl[{}]'.format(self.library.invoking_user)
        self.pe_patcher.start()

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:  # pragma: no cover
            # we likely never created the file.
            pass
        self.pe_patcher.stop()

    def test_perms_block_run(self):
        ''' Test that non-root can't run the important functions. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=False):
            with self.assertRaises(SystemExit) as fail_run, \
                    mock.patch('sys.stdout', new=StringIO()):
                oneoff.run([])
            self.assertEqual(fail_run.exception.code, 2)

    def test_run_nolocks(self):
        ''' Test that "run" fires when there are no locks. '''
        with mock.patch('os.execvpe') as mock_exec:
            self.library.run([])
        mock_exec.assert_called_once_with('puppet', ['puppet', 'agent', '--verbose', '--onetime',
                                                     '--no-daemonize', '--no-splay'],
                                          env={'PATH': self.library.puppet_bin_path})

    def test_run_nolocks_with_args(self):
        ''' Test that "run" passes args along. '''
        with mock.patch('os.execvpe') as mock_exec:
            self.library.run(['--nonsense1', '--shenanigans2'])
        mock_exec.assert_called_once_with('puppet', ['puppet', 'agent', '--verbose', '--onetime',
                                                     '--no-daemonize', '--no-splay',
                                                     '--nonsense1', '--shenanigans2'],
                                          env={'PATH': self.library.puppet_bin_path})

    def test_run_not_our_locks(self):
        ''' Test that "run" does nothing when we have no locks, but others do. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled 1h')
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+90*60, 'I nooped 2h')
        with self.assertRaises(SystemExit) as fail_run:
            with mock.patch('sys.stdout', new=StringIO()):
                self.library.run([])
        self.assertEqual(fail_run.exception.code, 0)
        # We don't test the stdout result here because of isatty and py2.
        # We could extend this once we're pure py3

    def test_run_disable_lock_tty(self):
        ''' Test that "run" does nothing when I have a lock, and tells me. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                                   now+30*60, 'It is my lock')
        with self.assertRaises(SystemExit) as fail_run:
            # Order matters here: isatty comes second since we are touching stdout twice.
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch('sys.stdout.isatty', return_value=True):
                self.library.run([])
        self.assertEqual(fail_run.exception.code, 0)
        self.assertIn('Puppet has been disabled', fake_out.getvalue())

    def test_run_disable_lock_notty(self):
        ''' Test that "run" does nothing when I have a lock, and is silent '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                                   now+30*60, 'It is my lock')
        with self.assertRaises(SystemExit) as fail_run:
            # Order matters here: isatty comes second since we are touching stdout twice.
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch('sys.stdout.isatty', return_value=False):
                self.library.run([])
        self.assertEqual(fail_run.exception.code, 0)
        self.assertEqual('', fake_out.getvalue())

    def test_run_noop_lock(self):
        ''' Test that "run" fires noop mode I have a noop lock. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'nooperate',
                                                   now+30*60, 'It is my lock')
        with mock.patch('os.execvpe') as mock_exec:
            self.library.run([])
        mock_exec.assert_called_once_with('puppet', ['puppet', 'agent', '--verbose', '--onetime',
                                                     '--no-daemonize', '--no-splay', '--noop'],
                                          env={'PATH': self.library.puppet_bin_path})
