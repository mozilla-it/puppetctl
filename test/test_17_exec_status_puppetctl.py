'''
    PuppetctlExecution test script for status of puppetctl (not puppet)
'''

import unittest
import os
import time
from io import StringIO
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlStatefile, PuppetctlExecution


class TestExecutionStatusPuppetctl(unittest.TestCase):
    ''' Class of tests about executing puppetctl status commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-status-puppet-statefile-mods.test.txt'
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = f'testingpuppetctl[{self.library.invoking_user}]'

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:
            # we likely never created the file.
            pass

    def test_status_puppetctl_nolocks(self):
        ''' Test the status of puppetctl, no locks.  Valid with or without root. '''
        result = self.library._status_of_puppetctl()
        self.assertIn('message', result)
        self.assertIn('Puppet is enabled and in operating mode', result['message'])
        self.assertIn('color', result)
        self.assertIsNone(result['color'])

    def test_status_puppetctl_disable(self):
        ''' Test the status of puppetctl, disable lock.  Valid with or without root. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled it')
        result = self.library._status_of_puppetctl()
        self.assertIn('message', result)
        self.assertIn('Puppet has been disabled', result['message'])
        self.assertIn('somebody2', result['message'])
        self.assertIn('I disabled it', result['message'])
        self.assertIn('color', result)
        self.assertIsNotNone(result['color'])

    def test_status_puppetctl_nooperate(self):
        ''' Test the status of puppetctl, noop lock.  Valid with or without root. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+30*60, 'I nooped it')
        result = self.library._status_of_puppetctl()
        self.assertIn('message', result)
        self.assertIn('Puppet is in nooperate mode', result['message'])
        self.assertIn('somebody3', result['message'])
        self.assertIn('I nooped it', result['message'])
        self.assertIn('color', result)
        self.assertIsNotNone(result['color'])

    def test_status_puppetctl_multilock(self):
        ''' Test the status of puppetctl, noop and disable locks.  Valid with or without root. '''
        now = int(time.time())
        with mock.patch.object(PuppetctlStatefile, '_allowed_to_write_statefile',
                               return_value=True):
            self.library.statefile_object.add_lock('somebody2', 'disable',
                                                   now+30*60, 'I disabled it')
            self.library.statefile_object.add_lock('somebody3', 'nooperate',
                                                   now+30*60, 'I nooped it')
        result = self.library._status_of_puppetctl()
        self.assertIn('message', result)
        self.assertIn('Puppet has been disabled', result['message'])
        self.assertIn('somebody2', result['message'])
        self.assertIn('I disabled it', result['message'])
        self.assertIn('Puppet is in nooperate mode', result['message'])
        self.assertIn('somebody3', result['message'])
        self.assertIn('I nooped it', result['message'])
        self.assertIn('color', result)
        self.assertIsNotNone(result['color'])

    def test_lock_status_call(self):
        '''
            This is not an interesting test.  The real work is done in _status_of_puppetctl,
            so this is just for coverage.
        '''
        with mock.patch('sys.stdout', new=StringIO()), \
                mock.patch.object(PuppetctlExecution, '_status_of_puppetctl') as mock_pc:
            self.library.lock_status()
        mock_pc.assert_called_once()

    def test_motd_status_call(self):
        '''
            Make sure that we print nothing when there's no errors.
        '''
        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as mock_motd, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, '_status_of_puppetctl',
                                  return_value={'message': 'foo', 'color': None,
                                                'disable': 0, 'nooperate': 0}) as mock_pc:
            self.library.motd_status()
        mock_pc.assert_called_once()
        self.assertEqual('', fake_out.getvalue())
        self.assertEqual(mock_motd.exception.code, 0)

        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as mock_motd, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, '_status_of_puppetctl',
                                  return_value={'message': 'foo', 'color': '1;31',
                                                'disable': 1, 'nooperate': 0}) as mock_pc:
            self.library.motd_status()
        mock_pc.assert_called_once()
        self.assertIn('foo', fake_out.getvalue())
        self.assertEqual(mock_motd.exception.code, 0)
