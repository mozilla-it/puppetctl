'''
    PuppetctlExecution.enable test script
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


class TestExecutionEnable(unittest.TestCase):
    ''' Class of tests about executing puppetctl enable commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-enable-statefile-mods.test.txt'
        self.pe_patcher = mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                                            return_value=True)
        self.sf_patcher = mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                                            return_value=True)
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = 'testingpuppetctl[{}]'.format(self.library.invoking_user)
        self.pe_patcher.start()
        self.sf_patcher.start()

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:  # pragma: no cover
            # we likely never created the file.
            pass
        self.pe_patcher.stop()
        self.sf_patcher.stop()

    def test_perms_block_enable(self):
        ''' Test that non-root can't run the important functions. '''
        oneoff = PuppetctlExecution(self.test_statefile)
        with mock.patch.object(PuppetctlExecution, '_allowed_to_run_command',
                               return_value=False):
            with self.assertRaises(SystemExit) as fail_enable, \
                    mock.patch('sys.stdout', new=StringIO()):
                oneoff.enable()
            self.assertEqual(fail_enable.exception.code, 2)

    def test_enable_nolocks(self):
        ''' Test that "enable" does nothing when there are no locks. '''
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.enable()
        self.assertIn('Puppet is already enabled.', fake_out.getvalue())

    def test_enable_not_our_locks(self):
        ''' Test that "enable" does nothing when we have no locks, but others do. '''
        now = int(time.time())
        self.library.statefile_object.add_lock('somebody2', 'disable', now+30*60, 'I disabled 1h')
        self.library.statefile_object.add_lock('somebody3', 'nooperate', now+90*60, 'I nooped 2h')
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.enable()
        self.assertIn('Puppet is already enabled.', fake_out.getvalue())

    def test_enable_disable_mylock(self):
        ''' Test that "enable" wants to enable when it's my lock. '''
        now = int(time.time())
        self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                               now+30*60, 'It is my lock')
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.enable()
        self.assertIn('Puppet has been enabled.', fake_out.getvalue())

    def test_enable_noop_mylock(self):
        ''' Test that "enable" assists, but doesn't enable, when there's a noop lock. '''
        now = int(time.time())
        self.library.statefile_object.add_lock(self.library.invoking_user, 'nooperate',
                                               now+30*60, 'It is my lock')
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.enable()
        self.assertIn('Puppet is enabled, but is in nooperate mode.', fake_out.getvalue())

    def test_enable_fails_remove_lock(self):
        ''' Test that "enable" complains if it can't remove the lock. '''
        now = int(time.time())
        self.library.statefile_object.add_lock(self.library.invoking_user, 'disable',
                                               now+30*60, 'It is my lock')
        with mock.patch.object(PuppetctlStatefile, 'remove_lock', return_value=False), \
                self.assertRaises(SystemExit) as lockfail, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.enable()
        self.assertIn('Unable to remove', fake_out.getvalue())
        self.assertEqual(lockfail.exception.code, 2)
