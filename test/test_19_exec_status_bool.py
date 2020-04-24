'''
    PuppetctlExecution test script, is-enabled and is-operating
'''

import unittest
import os
import time
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile, PuppetctlExecution


class TestExecutionStatusBool(unittest.TestCase):
    ''' Class of tests about is-enabled and is-operating puppetctl commands. '''

    # Here in the setup, override our statefile object's read command.
    # We fully test that in another test suite, so assume it works and
    # just let us shoot out the dict that would come from that func.
    # Since the state file is the basis of all our decisionmaking,
    # stomping that one function should cover all our state worries.
    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/unused-statefile.txt'
        self.library = PuppetctlExecution(self.test_statefile)

    def tearDown(self):
        ''' Cleanup test rig '''
        os.remove(self.test_statefile)

    def test_is_enabled(self, ):
        ''' Test the is_enabled function '''
        self.assertTrue(self.library.is_enabled())
        self.assertTrue(self.library.is_enabled('somebody1'))
        self.assertTrue(self.library.is_enabled('somebody2'))
        self.assertTrue(self.library.is_enabled('somebody3'))
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled 1h')
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+90*60, 'I nooped 2h')
        self.assertFalse(self.library.is_enabled())
        self.assertTrue(self.library.is_enabled('somebody1'))
        self.assertFalse(self.library.is_enabled('somebody2'))
        self.assertTrue(self.library.is_enabled('somebody3'))

    def test_is_operating(self, ):
        ''' Test the is_operating function '''
        self.assertTrue(self.library.is_operating())
        self.assertTrue(self.library.is_operating('somebody1'))
        self.assertTrue(self.library.is_operating('somebody2'))
        self.assertTrue(self.library.is_operating('somebody3'))
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled 1h')
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+90*60, 'I nooped 2h')
        self.assertFalse(self.library.is_operating())
        self.assertTrue(self.library.is_operating('somebody1'))
        self.assertTrue(self.library.is_operating('somebody2'))
        self.assertFalse(self.library.is_operating('somebody3'))
