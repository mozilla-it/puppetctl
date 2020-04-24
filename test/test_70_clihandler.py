'''
    PuppetctlCLIHandler test script
'''

import unittest
import sys
import os
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlExecution, PuppetctlCLIHandler
if sys.version_info.major >= 3:
    import configparser  # pragma: no cover
    from io import StringIO  # pragma: no cover
else:
    from six.moves import configparser  # pragma: no cover
    from io import BytesIO as StringIO  # pragma: no cover


class TestCLIHandler(unittest.TestCase):
    ''' Class of tests about parsing the CLI inputs. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.library = PuppetctlCLIHandler()

    def test_init(self):
        ''' Verify that the self object was initialized '''
        self.assertIsInstance(self.library, PuppetctlCLIHandler)
        self.assertIsInstance(self.library.runner, PuppetctlExecution)

    def test_cli_main_help(self):
        ''' Check main offer help '''
        # No arguments = give help, and it's exit 1 because it's
        # a cli 'error'
        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as main_empty:
            self.library.main(['puppetctl'])
        self.assertEqual(main_empty.exception.code, 1)
        # help via option = give help, and it's exit 0 because it's
        # something you asked for (argparse does this)
        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as main_empty:
            self.library.main(['puppetctl', '--help'])
        self.assertEqual(main_empty.exception.code, 0)
        # help via subcommand = give help, and it's exit 0 because it's
        # something you asked for (we do this)
        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as main_empty:
            self.library.main(['puppetctl', 'help'])
        self.assertEqual(main_empty.exception.code, 0)

    def test_cli_simple_command_bad(self):
        ''' Check main for bad task name. '''
        # Bad command = exit.  Note that we capture stderr this time.
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as main_junk:
            self.library.main(['puppetctl', 'play-twister'])
        self.assertEqual(main_junk.exception.code, 2)

    def test_cli_config_bad(self):
        ''' Check main stops us with bad uses of the config file '''
        # --config with no filename and no args.  Note that we capture stderr this time.
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as main_junk:
            self.library.main(['puppetctl', '--config'])
        self.assertEqual(main_junk.exception.code, 2)
        # --config with a bad filename and no args.  Note that we capture stderr this time.
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as main_junk:
            self.library.main(['puppetctl', '--config', '/tmp/no-way-this-exists.txt'])
        self.assertEqual(main_junk.exception.code, 2)
        # --config with a good filename but no args.  Note that we capture stderr this time.
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as main_junk:
            self.library.main(['puppetctl', '--config', '/proc/cpuinfo'])
        self.assertEqual(main_junk.exception.code, 2)
        # --config with a good filename but bad command.  Note that we capture stderr this time.
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as main_junk:
            self.library.main(['puppetctl', '--config', '/proc/cpuinfo', 'play-risk'])
        self.assertEqual(main_junk.exception.code, 2)

    def test_cli_config_nonconf_good(self):
        ''' Check main for good task name and a config file that exists but is wrong.  '''
        # Basically this is "don't let a crap config get in the way"
        with mock.patch('sys.stdout', new=StringIO()), \
                mock.patch.object(PuppetctlCLIHandler, 'subcommand_disable') as mock_main:
            self.library.main(['puppetctl', '--config', '/proc/cpuinfo',
                               'disable', '-m', 'some reason'])
        mock_main.assert_called_once_with('puppetctl', 'disable', ['-m', 'some reason'])
        self.assertIsInstance(self.library.runner, PuppetctlExecution)
        self.assertEqual(self.library.runner.puppet_bin_path,
                         self.library.runner.defaults.get('puppet_bin_path')+':/bin:/usr/bin')
        self.assertEqual(self.library.runner.lastrunfile,
                         self.library.runner.defaults.get('lastrunfile'))
        self.assertEqual(self.library.runner.statefile_object.state_file,
                         self.library.runner.statefile_object.defaults.get('state_file'))

    def test_cli_config_conf_good(self):
        ''' Check main for good task name and a config file that is good.  '''
        config = configparser.RawConfigParser()
        config.add_section('puppet')
        config.set('puppet', 'puppet_bin_path', '/opt/somepath')
        config.set('puppet', 'lastrunfile', '/opt/puppetlabs.yaml')
        config.add_section('puppetctl')
        config.set('puppetctl', 'state_file', '/home/status')
        with open('/tmp/test_cli_config_nonconf_good.conf', 'w') as configfile:
            config.write(configfile)
        with mock.patch('sys.stdout', new=StringIO()), \
                mock.patch.object(PuppetctlCLIHandler, 'subcommand_disable') as mock_main:
            self.library.main(['puppetctl', '--config', '/tmp/test_cli_config_nonconf_good.conf',
                               'disable', '-m', 'some reason'])
        os.remove('/tmp/test_cli_config_nonconf_good.conf')
        mock_main.assert_called_once_with('puppetctl', 'disable', ['-m', 'some reason'])
        self.assertIsInstance(self.library.runner, PuppetctlExecution)
        self.assertEqual(self.library.runner.puppet_bin_path, '/opt/somepath:/bin:/usr/bin')
        self.assertEqual(self.library.runner.lastrunfile, '/opt/puppetlabs.yaml')
        self.assertEqual(self.library.runner.statefile_object.state_file, '/home/status')

    def test_cli_simple_command_good(self):
        ''' Check main for good task name.  This is not exhaustive. '''
        # Good command = try it
        with mock.patch('sys.stdout', new=StringIO()), \
                mock.patch.object(PuppetctlCLIHandler, 'subcommand_disable') as mock_main:
            self.library.main(['puppetctl', 'disable', '-m', 'some reason'])
        mock_main.assert_called_once_with('puppetctl', 'disable', ['-m', 'some reason'])
        self.assertIsInstance(self.library.runner, PuppetctlExecution)
        self.assertEqual(self.library.runner.puppet_bin_path,
                         self.library.runner.defaults.get('puppet_bin_path')+':/bin:/usr/bin')
        self.assertEqual(self.library.runner.lastrunfile,
                         self.library.runner.defaults.get('lastrunfile'))
        self.assertEqual(self.library.runner.statefile_object.state_file,
                         self.library.runner.statefile_object.defaults.get('state_file'))
