'''
    Test raw interactions with the state file - i.e literally check what ends up on disk.
'''

import unittest
import os
import test.context  # pylint: disable=unused-import
from puppetctl import PuppetctlStatefile


class TestRawReadStatefile(unittest.TestCase):
    ''' Class of tests about basic reading of a state file, usually the edge cases. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_reading_file = '/tmp/raw-reading-file.test.txt'
        self.library = PuppetctlStatefile(self.test_reading_file)

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_reading_file)
            os.remove(self.library.bogus_state_file)
        except OSError:
            # we likely never created the file.
            pass

    # Below are tests about reading the statefile.  Because it's about
    # reading an actual file, we don't use Mock here.
    def test_reading_not_a_file(self):
        ''' Verify we get a proper structure when no state file exists '''
        result = self.library._read_state_file()
        self.assertDictEqual(result, self.library.empty_state_file_contents)

    def test_reading_a_directory(self):
        ''' Verify we get a proper structure when sent not-a-file '''
        self.library.state_file = '/'
        result = self.library._read_state_file()
        self.assertDictEqual(result, self.library.empty_state_file_contents)

    def test_reading_error_not_json(self):
        ''' readable file but not json '''
        self.library.state_file = '/proc/cpuinfo'
        result = self.library._read_state_file()
        self.assertDictEqual(result, self.library.empty_state_file_contents)

    def test_reading_empty_file(self):
        ''' read an empty file '''
        # make a blank file:
        with open(self.test_reading_file, 'w') as _filepointer:
            pass
        # ... read it ...
        result = self.library._read_state_file()
        # and it should be empty because the func detects the issue and gives us simple json.
        self.assertDictEqual(result, self.library.empty_state_file_contents)

    def test_reading_json_file(self):
        ''' read a json file '''
        # make a simple json file.  the purpose of the _read is to return raw contents,
        # so this is a fair test because it doesn't matter that this structure isn't like
        # our actual statefile entries.
        with open(self.test_reading_file, 'w') as filepointer:
            filepointer.write('{\n   "foo": 123\n}\n')
        result = self.library._read_state_file()
        # check that we got back our one-off structure.
        self.assertDictEqual(result, {'foo': 123})

    def test_reading_bad_json(self):
        ''' reading a json file that's gotten corrupted '''
        # make valid json file but non-dict, meaning it's wrong.
        with open(self.test_reading_file, 'w') as filepointer:
            filepointer.write('[]\n')
        result = self.library._read_state_file()
        # Check that we get taken back to baseline
        self.assertDictEqual(result, self.library.empty_state_file_contents)
