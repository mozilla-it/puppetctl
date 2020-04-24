'''
    Test interactions with the state file, that lock edits happen as expected.
'''

import unittest
import os
import time
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile


class TestLockChanges(unittest.TestCase):
    ''' Class of tests about adding and removing locks. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_reading_file = '/tmp/lock-changes.test.txt'
        # Override the write blocker since we are writing to a test file
        self.sf_patcher = mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                                            return_value=True)
        self.library = PuppetctlStatefile(self.test_reading_file)
        self.sf_patcher.start()

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_reading_file)
        except OSError:
            # we likely never created the file.
            pass
        self.sf_patcher.stop()

    def test_garbage_adds(self):
        ''' Verify we can't add stupid locks '''
        now = int(time.time())
        with self.assertRaises(ValueError):
            self.library.add_lock('a_b@d_u$3rname', 'disable', now+60*60, message='This fails')
        with self.assertRaises(ValueError):
            self.library.add_lock('somebody1', 'dysable', now+60*60, message='This fails')
        with self.assertRaises(ValueError):
            self.library.add_lock('somebody1', 'disable', 'a date string', message='This fails')
        with self.assertRaises(ValueError):
            self.library.add_lock('somebody1', 'disable', now-60*60, message='This fails')
        with self.assertRaises(ValueError):
            self.library.add_lock('somebody1', 'disable', now+60*60, message=['this', 'fails'])

    def test_add_lock(self):
        ''' Verify we can add a lock '''
        # add a simple lock
        now = int(time.time())
        wresult = self.library.add_lock('somebody1', 'disable', now+60*60, message='This works')
        self.assertTrue(wresult)
        rresult = self.library._read_state_file()
        self.assertEqual(len(rresult.keys()), 1)

    def test_failed_lock(self):
        ''' pretend a lock write failed '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, 'write_state_file', return_value=False):
            wresult3 = self.library.add_lock('somebody3', 'disable', now+30*60, message='full disk')
        self.assertFalse(wresult3)

    def test_deny_dupe_locks(self):
        ''' Verify we cannot add multiple-per-person locks '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        wresult2 = self.library.add_lock('somebody1', 'disable', now+60*60, message='this fails')
        self.assertFalse(wresult2)
        rresult = self.library._read_state_file()
        self.assertEqual(len(rresult.keys()), 1)

    def test_add_differing_lock(self):
        ''' Verify one person can add multiple types of lock '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+60*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 1)
        wresult2 = self.library.add_lock('somebody1', 'nooperate', now+30*60, message='This works')
        self.assertTrue(wresult2)
        rresult2 = self.library._read_state_file()
        self.assertEqual(len(rresult2.keys()), 2)

    def test_removing_locks_exists(self):
        ''' Verify we can remove a lock for someone '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 1)
        wresult2 = self.library.remove_lock(wresult1)
        self.assertTrue(wresult2)
        rresult2 = self.library._read_state_file()
        self.assertEqual(len(rresult2.keys()), 0)

    def test_removing_multiple_locks(self):
        ''' Verify we can remove multiple locks at once '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        wresult2 = self.library.add_lock('somebody2', 'disable', now+30*60, message='This too')
        self.assertTrue(wresult2)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 2)
        lockkeys = list(rresult1.keys())
        wresult3 = self.library.remove_lock(lockkeys)
        self.assertTrue(wresult3)
        rresult2 = self.library._read_state_file()
        self.assertEqual(len(rresult2.keys()), 0)

    def test_removing_locks_nonexists(self):
        ''' Verify when there's a removal for a nonexistent lock '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 1)
        lockkey = 'nonsense_key_that_will_not_exist'
        with self.assertRaises(KeyError):
            self.library.remove_lock(lockkey)
        rresult2 = self.library._read_state_file()
        self.assertEqual(len(rresult2.keys()), 1)
        self.assertDictEqual(rresult1, rresult2)

    def test_get_disable_lockids(self):
        ''' Verify we get the correct lockids for someone '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 1)
        self.assertEqual(len(self.library.get_disable_lock_ids()), 1)
        self.assertEqual(len(self.library.get_disable_lock_ids('somebody1')), 1)
        self.assertEqual(self.library.get_disable_lock_ids(),
                         self.library.get_disable_lock_ids('somebody1'))
        self.assertEqual(self.library.get_disable_lock_ids('somebody2'), [])
        self.assertEqual(self.library.get_noop_lock_ids(), [])
        self.assertEqual(self.library.get_noop_lock_ids('somebody1'), [])
        self.assertEqual(self.library.get_noop_lock_ids('somebody2'), [])

    def test_get_noop_lockids(self):
        ''' Verify we get the correct lockids for someone '''
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'nooperate', now+30*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library._read_state_file()
        self.assertEqual(len(rresult1.keys()), 1)
        self.assertEqual(len(self.library.get_noop_lock_ids()), 1)
        self.assertEqual(len(self.library.get_noop_lock_ids('somebody1')), 1)
        self.assertEqual(self.library.get_noop_lock_ids(),
                         self.library.get_noop_lock_ids('somebody1'))
        self.assertEqual(self.library.get_noop_lock_ids('somebody2'), [])
        self.assertEqual(self.library.get_disable_lock_ids(), [])
        self.assertEqual(self.library.get_disable_lock_ids('somebody1'), [])
        self.assertEqual(self.library.get_disable_lock_ids('somebody2'), [])

    def test_get_lock_info(self):
        ''' Verify you can get info about a lock '''
        lockkey = 'nonsense_key_that_will_not_exist'
        self.assertEqual(self.library.get_lock_info(lockkey), '')
        now = int(time.time())
        wresult1 = self.library.add_lock('somebody1', 'disable', now+30*60, message='This works')
        self.assertTrue(wresult1)
        rresult1 = self.library.get_lock_info(wresult1)
        self.assertIn('Puppet has been disabled', rresult1)
        self.assertIn('somebody1', rresult1)
        self.assertIn('This works', rresult1)
        self.library.remove_lock(wresult1)

        wresult2 = self.library.add_lock('somebody2', 'nooperate', now+30*60, message='This worked')
        self.assertTrue(wresult2)
        rresult2 = self.library.get_lock_info(wresult2)
        self.assertIn('Puppet is in nooperate mode', rresult2)
        self.assertIn('somebody2', rresult2)
        self.assertIn('This worked', rresult2)
        self.library.remove_lock(wresult2)
