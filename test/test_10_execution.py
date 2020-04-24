'''
    PuppetctlExecution test script, the basics
'''

import unittest
import os
import test.context  # pylint: disable=unused-import
from puppetctl import PuppetctlStatefile, PuppetctlExecution


class TestExecutionClass(unittest.TestCase):
    ''' Class of tests about executing puppetctl commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec.test.txt'
        # This file is never created

    def test_plain_init(self):
        ''' Verify that the class inits with no parameters '''
        library = PuppetctlExecution()
        self.assertEqual(library.puppet_bin_path,
                         library.defaults.get('puppet_bin_path')+':/bin:/usr/bin')
        self.assertIsInstance(library.lastrunfile, str)
        self.assertEqual(library.lastrunfile, library.defaults.get('lastrunfile'))
        self.assertEqual(library.agent_catalog_run_lockfile,
                         library.defaults.get('agent_catalog_run_lockfile'))
        self.assertIsInstance(library.invoking_user, str)
        self.assertIsInstance(library.logging_tag, str)
        self.assertIsInstance(library.statefile_object, PuppetctlStatefile)

    def test_init_sudo(self):
        ''' Verify that the self object handles user edge-cases '''
        original_sudo = os.environ.get('SUDO_USER')
        original_user = os.environ.get('USER')
        os.environ.pop('SUDO_USER', None)
        os.environ.pop('USER', None)
        obj_unknown = PuppetctlExecution()
        self.assertEqual(obj_unknown.invoking_user, 'UNKNOWN')
        os.environ['USER'] = 'someguy'
        obj_user = PuppetctlExecution()
        self.assertEqual(obj_user.invoking_user, 'someguy')
        os.environ['SUDO_USER'] = 'otherguy'
        obj_sudo = PuppetctlExecution()
        self.assertEqual(obj_sudo.invoking_user, 'otherguy')
        os.environ['USER'] = original_user
        # no cover begins here because the resets vary based on who you tested as.
        # This is just to put the house back in order.
        if original_sudo is None:  # pragma: no cover
            os.environ.pop('SUDO_USER', None)
        else:  # pragma: no cover
            os.environ['SUDO_USER'] = original_sudo

    def test_init_statefile_pos(self):
        ''' Verify the object was initialized with a state file, positional arg '''
        library = PuppetctlExecution(self.test_statefile)
        self.assertEqual(library.statefile_object.state_file, self.test_statefile)

    def test_init_statefile_kwarg(self):
        ''' Verify the object was initialized with a state file, kwarg arg '''
        library = PuppetctlExecution(state_file=self.test_statefile)
        self.assertEqual(library.statefile_object.state_file, self.test_statefile)

    def test_execution_allargs_pos(self):
        ''' Verify that the class inits positionally '''
        library = PuppetctlExecution('/tmp/somestate1', '/somepath1:/bin',
                                     '/opt/here1/last_run_summary.yaml', '/tmp/a.lock')
        self.assertEqual(library.puppet_bin_path, '/somepath1:/bin:/usr/bin')
        self.assertEqual(library.lastrunfile, '/opt/here1/last_run_summary.yaml')
        self.assertEqual(library.agent_catalog_run_lockfile, '/tmp/a.lock')
        self.assertIsInstance(library.invoking_user, str)
        self.assertIsInstance(library.logging_tag, str)
        self.assertIsInstance(library.statefile_object, PuppetctlStatefile)
        self.assertEqual(library.statefile_object.state_file, '/tmp/somestate1')

    def test_execution_allargs_kwargs(self):
        ''' Verify that the class inits with kwargs '''
        library = PuppetctlExecution(state_file='/tmp/somestate2',
                                     puppet_bin_path='/somepath2',
                                     lastrunfile='/opt/puppet/somewhere2/last_run_summary.yaml',
                                     agent_catalog_run_lockfile='/tmp/my.lck')
        self.assertEqual(library.puppet_bin_path, '/somepath2:/bin:/usr/bin')
        self.assertEqual(library.lastrunfile, '/opt/puppet/somewhere2/last_run_summary.yaml')
        self.assertEqual(library.agent_catalog_run_lockfile, '/tmp/my.lck')
        self.assertIsInstance(library.invoking_user, str)
        self.assertIsInstance(library.logging_tag, str)
        self.assertIsInstance(library.statefile_object, PuppetctlStatefile)
        self.assertEqual(library.statefile_object.state_file, '/tmp/somestate2')
