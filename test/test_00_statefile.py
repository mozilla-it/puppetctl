'''
    Test raw spinup of the state file object
'''

import unittest
import test.context  # pylint: disable=unused-import
from puppetctl import PuppetctlStatefile


class TestRawReadStatefile(unittest.TestCase):
    ''' Class of tests about basic reading of a state file, usually the edge cases. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/status.test.txt'
        # This file is never created

    def test_plain_init(self):
        ''' Verify that the class inits with no parameters '''
        library = PuppetctlStatefile()
        self.assertEqual(library.state_file, library.defaults.get('state_file'))
        self.assertIsInstance(library.statefile_locktypes, list)
        self.assertGreater(len(library.statefile_locktypes), 0)
        self.assertEqual(library.empty_state_file_contents, {})

    def test_init_statefile_pos(self):
        ''' Verify the object was initialized with a state file, positional arg '''
        library = PuppetctlStatefile(self.test_statefile)
        self.assertEqual(library.state_file, self.test_statefile)

    def test_init_statefile_kwarg(self):
        ''' Verify the object was initialized with a state file, kwarg arg '''
        library = PuppetctlStatefile(state_file=self.test_statefile)
        self.assertEqual(library.state_file, self.test_statefile)
