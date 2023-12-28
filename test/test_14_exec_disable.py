'''
    PuppetctlExecution.disable test script
'''

import unittest
import os
import time
from io import StringIO
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile, PuppetctlExecution


class TestExecutionDisable(unittest.TestCase):
    ''' Class of tests about executing puppetctl disable commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-disable-statefile-mods.test.txt'
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = 'testingpuppetctl[{}]'.format(self.library.invoking_user)

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:  # pragma: no cover
            # we likely never created the file.
            pass

    def test_perms_block_disable(self):
        ''' Test that non-root can't run the important functions. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=False):
            with self.assertRaises(SystemExit) as fail_disable, \
                    mock.patch('sys.stdout', new=StringIO()):
                oneoff.disable(False, int(time.time()+60), 'failure testing')
            self.assertEqual(fail_disable.exception.code, 2)

    def test_disable_nolocks(self):
        ''' Test that "disable" disables when there are no locks and no puppet running '''
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                      return_value={}), \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=False, expiry=int(time.time())+60*60, message='')
        self.assertIn('Puppet has been disabled', fake_out.getvalue())

    def test_disable_nolocks_puppetrun(self):
        ''' Test that "disable" disables when there are no locks but puppet is running '''
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_puppet_processes_running',
                                      return_value={'2468': 'mock-puppet agent --no-splay'}), \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=False, expiry=int(time.time())+60*60, message='')
        self.assertIn('mock-puppet agent --no-splay', fake_out.getvalue())
        self.assertIn('If you need to stop an active puppet run from finishing',
                      fake_out.getvalue())
        self.assertIn('Puppet has been disabled', fake_out.getvalue())

    def test_disable_not_our_locks(self):
        ''' Test that "disable" does disables when we have no locks, but others do. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled 1h')
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+90*60, 'I nooped 2h')
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=False, expiry=int(time.time())+60*60, message='')
        self.assertIn('Puppet has been disabled', fake_out.getvalue())

    def test_disable_disable_mylock(self):
        ''' Test that "disable" refuses to disable when it's my lock. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                                   now+30*60, 'It is my lock')
        with self.assertRaises(SystemExit) as catch_noforce:
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=False, expiry=int(time.time())+60*60, message='')
        self.assertIn('Puppet is already disabled', fake_out.getvalue())
        self.assertEqual(catch_noforce.exception.code, 1)

    def test_disable_force_mylock(self):
        ''' Test that "disable" disables when I force a lock. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                                   now+30*60, 'old lock')
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=True, expiry=int(time.time())+60*60, message='new lock')
        self.assertIn('Puppet has been disabled', fake_out.getvalue())
        self.assertIn('new lock', fake_out.getvalue())

    def test_disable_noop_mylock(self):
        ''' Test that "disable" stomps when there's a noop lock. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'nooperate',
                                                   now+30*60, 'old lock')
            with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                    mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                      return_value=True):
                self.library.disable(force=False, expiry=int(time.time())+60*60, message='new lock')
        self.assertIn('Puppet has been disabled', fake_out.getvalue())
        self.assertIn('new lock', fake_out.getvalue())

    def test_disable_fail_add_lock(self):
        ''' Test that "disable" complains if it can't add a lock '''
        with mock.patch.object(PuppetctlStatefile, 'add_lock', return_value=False), \
                self.assertRaises(SystemExit) as lockfail, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                  return_value=True):
            self.library.disable(force=False, expiry=int(time.time())+60*60, message='lock')
        self.assertEqual(lockfail.exception.code, 2)
        self.assertIn('Unable to add lock', fake_out.getvalue())

    def test_disable_failremovedisable(self):
        ''' Test that "disable" complains if it can't force in a new lock. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                                   now+30*60, 'It is my lock')
        with mock.patch.object(PuppetctlStatefile, 'remove_lock', return_value=False), \
                self.assertRaises(SystemExit) as lockfail, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                  return_value=True):
            self.library.disable(force=True, expiry=int(time.time())+60*60, message='new lock')
        self.assertIn('Unable to remove', fake_out.getvalue())
        self.assertEqual(lockfail.exception.code, 2)

    def test_disable_failremovenoop(self):
        ''' Test that "disable" complains if it can't override noop locks. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock(self.library.invoking_user, 'nooperate',
                                                   now+30*60, 'It is my lock')
        with mock.patch.object(PuppetctlStatefile, 'remove_lock', return_value=False), \
                self.assertRaises(SystemExit) as lockfail, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                  return_value=True):
            self.library.disable(force=False, expiry=int(time.time())+60*60, message='new lock')
        self.assertIn('Unable to remove', fake_out.getvalue())
        self.assertEqual(lockfail.exception.code, 2)
