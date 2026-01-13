'''
    PuppetctlExecution.break_all_locks test script
'''

import unittest
import os
from io import StringIO
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile, PuppetctlExecution


class TestExecutionBreakAllLocks(unittest.TestCase):
    ''' Class of tests about executing puppetctl break_all_locks commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-break_all_locks-statefile-mods.test.txt'
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = f'testingpuppetctl[{self.library.invoking_user}]'

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:  # pragma: no cover
            # we likely never created the file.
            pass

    def test_nothing_to_do(self):
        ''' Test that we do nothing if there aren't locks to break. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=True), \
                mock.patch.object(PuppetctlExecution, 'is_operating', return_value=True), \
                self.assertRaises(SystemExit) as fail_break, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            oneoff.break_all_locks(2)
        self.assertIn('There are no locks', fake_out.getvalue())
        self.assertEqual(fail_break.exception.code, 0)

    def test_perms_block_break(self):
        ''' Test that non-root can't run the important functions. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=False), \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False), \
                self.assertRaises(SystemExit) as fail_break, \
                mock.patch('sys.stdout', new=StringIO()):
            oneoff.break_all_locks(2)
        self.assertEqual(fail_break.exception.code, 2)

    def test_break_bad_parameters(self):
        ''' Test that 'break_all_locks' fails if double-force isn't applied. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False):
            with self.assertRaises(SystemExit) as fail_break_weak_force0, \
                    mock.patch('sys.stdout', new=StringIO()):
                self.library.break_all_locks(0)
            self.assertEqual(fail_break_weak_force0.exception.code, 2)
            with self.assertRaises(SystemExit) as fail_break_weak_force1, \
                    mock.patch('sys.stdout', new=StringIO()):
                self.library.break_all_locks(1)
            self.assertEqual(fail_break_weak_force1.exception.code, 2)
            with self.assertRaises(SystemExit) as fail_break_weirdparam, \
                    mock.patch('sys.stdout', new=StringIO()):
                self.library.break_all_locks(True)
            self.assertEqual(fail_break_weirdparam.exception.code, 2)

    def test_break_good_no_write(self):
        ''' Test that 'break_all_locks' fails if somehow we can't write the file. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False), \
                mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                                  return_value=False):
            with self.assertRaises(SystemExit) as fail_break_writing, \
                    mock.patch('time.sleep'), \
                    mock.patch('sys.stdout', new=StringIO()):
                self.library.break_all_locks(2)
            self.assertEqual(fail_break_writing.exception.code, 2)

    def test_break_good(self):
        ''' Test that 'break_all_locks' can work. '''
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=True), \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False), \
                mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                                  return_value=True):
            # make sure there's a file there, or our reset count will be > 1
            # below during the actual test.
            self.library.statefile_object.reset_state_file()
            # "Hey, you're not testing with locks!"  Yeah.  Since we're stomping all
            # locks it doesn't really matter what was in it before.
            with mock.patch.object(PuppetctlStatefile, 'reset_state_file') as mock_reset, \
                    mock.patch('time.sleep'), \
                    mock.patch('sys.stdout', new=StringIO()):
                self.library.break_all_locks(2)
            mock_reset.assert_called_once_with()
