'''
    Test read-and-write interactions with the state file. Not really concerned with
    WHAT is in the file so much as it reads and writes items to the state file.
'''

import unittest
import os
import json
import time
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile


class TestCookedReadStatefile(unittest.TestCase):
    ''' Class of tests about reading the state file fully. '''

    def setUp(self):
        ''' Preparing test rig '''
        # Our tests need to use dynamic timing, because the locks will clear
        # when they are expired.  We're running this with 2 valid locks and
        # one expired one.
        # We raw-create the file because we are testing the read-write functions
        self.test_reading_file = '/tmp/cooked-reading-file.test.txt'
        self.library = PuppetctlStatefile(self.test_reading_file)
        now = int(time.time())
        self.locks = {
            '24682468': {'message': 'I should be expired', 'locktype': 'nooperate',
                         'time_begin': now-90*60, 'time_expiry': now-30*60, 'user': 'username1'},
            'whodoyou': {'message': 'I disabled 1h', 'locktype': 'disabled',
                         'time_begin': now-30*60, 'time_expiry': now+30*60, 'user': 'username2'},
            'appreci8': {'message': 'I nooped 2h', 'locktype': 'nooperate',
                         'time_begin': now-30*60, 'time_expiry': now+90*60, 'user': 'username3'},
        }

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_reading_file)
        except OSError:
            # we likely never created the file.
            pass

    def test_reading_cooked(self):
        ''' Verify we get a proper structure when there's an expired lock '''
        self.assertFalse(os.path.exists(self.test_reading_file))
        with open(self.test_reading_file, 'w') as filepointer:
            json.dump(self.locks, filepointer)
        # Call the reading function.
        result = self.library.read_state_file()  # public
        # Since there's an expired lock it should be culled to only the good ones
        goodlocks = {k: self.locks[k] for k in self.locks if k in ['whodoyou', 'appreci8']}
        self.assertDictEqual(result, goodlocks)

    def test_writing_nonroot(self):
        ''' Verify nonroot can't write '''
        self.assertFalse(os.path.exists(self.test_reading_file))
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=False):
            wresult = self.library.write_state_file(self.locks)
        self.assertFalse(wresult)
        self.assertFalse(os.path.exists(self.test_reading_file))

    def test_writing_with_privs(self):
        ''' Verify we read and write '''
        self.assertFalse(os.path.exists(self.test_reading_file))
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            wresult = self.library.write_state_file(self.locks)
        self.assertTrue(wresult)
        self.assertTrue(os.path.exists(self.test_reading_file))

    def test_resetting_file(self):
        ''' Verify we reset a statefile properly '''
        with mock.patch.object(PuppetctlStatefile, 'write_state_file', return_value=True):
            result1 = self.library.reset_state_file()
        self.assertTrue(result1)
        with mock.patch.object(PuppetctlStatefile, 'write_state_file', side_effect=IOError):
            result2 = self.library.reset_state_file()
        self.assertFalse(result2)
