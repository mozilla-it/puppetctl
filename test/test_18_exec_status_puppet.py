'''
    PuppetctlExecution test script for status of puppet (not puppetctl)
'''

import unittest
import sys
import os
import time
import subprocess
import test.context  # pylint: disable=unused-import
import six
import mock
from puppetctl import PuppetctlExecution
if sys.version_info.major >= 3:
    from io import StringIO  # pragma: no cover
else:
    from io import BytesIO as StringIO  # pragma: no cover


class TestExecutionStatusPuppet(unittest.TestCase):
    ''' Class of tests about executing puppetctl status commands. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.test_statefile = '/tmp/exec-status-puppetctl-statefile-mods.test.txt'
        self.library = PuppetctlExecution(self.test_statefile)
        self.library.logging_tag = 'testingpuppetctl[{}]'.format(self.library.invoking_user)

    def tearDown(self):
        ''' Cleanup test rig '''
        try:
            os.remove(self.test_statefile)
        except OSError:
            # we likely never created the file.
            pass

    def test_parse_lastrunfile(self):
        ''' Run our test files through _parse_puppet_lastrunfile '''
        devnull = open(os.devnull, 'w')
        retcode = subprocess.call(['ruby', '--version'],
                                  env={'PATH': self.library.puppet_bin_path}, stdout=devnull)
        if retcode != 0:  # pragma: no cover
            self.skipTest('Cannot test without the puppet ruby environment')
        devnull.close()
        mydir = os.path.dirname(__file__)

        cleanfile = os.path.join(mydir, 'last_run_summary', 'clean_last_run_summary.yaml')
        cleancodes = self.library._parse_puppet_lastrunfile(cleanfile)
        # The values here are visually copied from the files in test/last_run_summary/*
        age = int(time.time()) - 1586995296
        nearage = [age-1, age, age+1]
        self.assertIn(cleancodes['age'], nearage)
        self.assertEqual(cleancodes['errors'], 0)
        self.assertEqual(cleancodes['config'], 'a294ac4f4fcd5264e5246df0787757a74fc3d966')

        onefailfile = os.path.join(mydir, 'last_run_summary', 'fail_one_last_run_summary.yaml')
        onefailcodes = self.library._parse_puppet_lastrunfile(onefailfile)
        # The values here are visually copied from the files in test/last_run_summary/*
        age = int(time.time()) - 1587278457
        nearage = [age-1, age, age+1]
        self.assertIn(onefailcodes['age'], nearage)
        self.assertEqual(onefailcodes['errors'], 1)
        self.assertEqual(onefailcodes['config'], '3a3d5827a1637456d360f888462d2aa0dbd975f6')

    def test_status_puppet(self):
        ''' Emulate testing the status of puppet '''
        with mock.patch('os.geteuid', return_value=0), \
                mock.patch('os.path.exists', return_value=True), \
                mock.patch.object(PuppetctlExecution, '_parse_puppet_lastrunfile') as mock_parse:
            self.library._status_of_puppet('/tmp/pretend-i-exist.txt')
        mock_parse.assert_called_once_with('/tmp/pretend-i-exist.txt')

    def test_status_puppet_nonroot(self):
        ''' Emulate testing the status of puppet when not root '''
        with mock.patch('os.geteuid', return_value=1006), \
                mock.patch('os.path.exists', return_value=True), \
                mock.patch.object(PuppetctlExecution, '_parse_puppet_lastrunfile') as mock_parse:
            self.library._status_of_puppet('/tmp/pretend-i-exist.txt')
        mock_parse.assert_not_called()

    def test_status_puppet_nofile(self):
        ''' Emulate testing the status of puppet when the file doesn't exist '''
        with mock.patch('os.geteuid', return_value=0), \
                mock.patch('os.path.exists', return_value=False), \
                mock.patch.object(PuppetctlExecution, '_parse_puppet_lastrunfile') as mock_parse:
            self.library._status_of_puppet('/tmp/pretend-i-exist.txt')
        mock_parse.assert_not_called()

    def test_main_status_call(self):
        '''
            This is not an interesting test.  The real work is done in _status_of_puppet
            and _status_of_puppetctl, so this is just for coverage.
        '''
        with self.assertRaises(SystemExit) as status_run:
            with mock.patch('sys.stdout', new=StringIO()), \
                    mock.patch.object(PuppetctlExecution, '_status_of_puppet') as mock_p, \
                    mock.patch.object(PuppetctlExecution, '_status_of_puppetctl') as mock_pc:
                self.library.status()
        self.assertIn(status_run.exception.code, [0, 1])
        mock_p.assert_called_once()
        mock_pc.assert_called_once()

    def test_puppet_process_detect(self):
        ''' Test our detection of a running puppet process. '''
        # If we're not root, we can't check.
        with mock.patch('os.geteuid', return_value=1006):
            result = self.library._puppet_processes_running('/tmp/whocares.txt')
        self.assertEqual(result, {})
        # If we are root, and the file isn't there, we can't do anything.
        with mock.patch('os.geteuid', return_value=0):
            result = self.library._puppet_processes_running('/tmp/whocares.txt')
        self.assertEqual(result, {})

        # Make a sample lock, that we'll use on the rest of the tests.
        sample_pid = '13579'
        test_lockfile = '/tmp/process_detect_pid.lock'
        with open(test_lockfile, 'w') as writelock:
            writelock.write(sample_pid)
        fake_os_stat = os.stat('/')

        # All future checks have root privs
        with mock.patch('os.geteuid', return_value=0):

            with mock.patch.object(six.moves.builtins, 'open',
                                   mock.mock_open(read_data='not_a_pid')):
                result = self.library._puppet_processes_running(test_lockfile)
            self.assertEqual(result, {})

            # Pretend we get something from the lockfile, but the command
            # has exited between then and the time we look in /proc.
            with mock.patch('os.stat', side_effect=OSError):
                result = self.library._puppet_processes_running(test_lockfile)
            self.assertEqual(result, {})

            # Pretend that the pid in the lockfile is somehow a process
            # not owned by root.
            with mock.patch('os.stat') as mock_oss:
                mock_oss.return_value.st_uid.return_value = 1020
                result = self.library._puppet_processes_running(test_lockfile)
            self.assertEqual(result, {})

            # All future tests have a pid, a root-owned process in /proc...
            with mock.patch('os.stat', return_value=fake_os_stat):
                # ... and because we're about to take over the 'open' call, we have
                # to replace the inital call from where we read the pid the first time.
                # This makes the handlers messy to read.
                #
                # Pretend that the proc has disappeared in the sliver of
                # time between the time we stat'ed it.
                with mock.patch.object(six.moves.builtins, 'open') as mopen:
                    handlers = (mock.mock_open(read_data=sample_pid).return_value,
                                IOError)
                    mopen.side_effect = handlers
                    result = self.library._puppet_processes_running(test_lockfile)
                self.assertEqual(result, {})

                # Pretend that the proc is somehow not puppet.
                with mock.patch.object(six.moves.builtins, 'open') as mopen:
                    handlers = (mock.mock_open(read_data=sample_pid).return_value,
                                mock.mock_open(read_data='echo\0some\0string\0').return_value)
                    mopen.side_effect = handlers
                    result = self.library._puppet_processes_running(test_lockfile)
                self.assertEqual(result, {})

                # FINALLY.  Pretend that this was an actual puppet run.
                with mock.patch.object(six.moves.builtins, 'open') as mopen:
                    handlers = (mock.mock_open(read_data=sample_pid).return_value,
                                mock.mock_open(read_data=('/opt/puppetlabs/puppet/bin/ruby\0'
                                                          '/opt/puppetlabs/puppet/bin/puppet\0'
                                                          'agent\0--verbose\0--onetime\0'
                                                          '--no-daemonize\0--no-splay\0'
                                                          '')).return_value)
                    mopen.side_effect = handlers
                    result = self.library._puppet_processes_running(test_lockfile)
                self.assertIn(sample_pid, result)
                self.assertIn('puppet agent', result[sample_pid])
