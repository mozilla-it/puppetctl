'''
    PuppetctlCLIHandler test script
'''

import unittest
import sys
import os
import time
import argparse
import test.context  # pylint: disable=unused-import
from puppetctl import PuppetctlExecution, PuppetctlCLIHandler
if sys.version_info.major >= 3:
    import configparser  # pragma: no cover
else:
    from six.moves import configparser  # pragma: no cover


class TestCLIHandler(unittest.TestCase):
    ''' Class of tests about parsing the CLI inputs. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.library = PuppetctlCLIHandler()

    def test_init(self):
        ''' Verify that the self object was initialized '''
        self.assertIsInstance(self.library, PuppetctlCLIHandler)
        self.assertIsInstance(self.library.runner, PuppetctlExecution)

    def test_time_parser(self):
        ''' Test the _uniform_time_parser function '''
        # The expected return from this function is an expiry time in epoch seconds.
        # It's represented as 'now + some time'.  But, of course, 'now' is moving.
        # Due to rounding and time involved in running the tests themselves, we're going
        # to have the checks give 1-second slop in either direction.  Our tests are about
        # 'do you get a correct-ish answer' more than them being exactingly precise.
        def _when(modifier):
            when = int(time.time()) + modifier
            return [when-1, when, when+1]

        parser = argparse.ArgumentParser()
        dategroup = parser.add_mutually_exclusive_group()
        dategroup.add_argument('--time', '-t', type=str, required=False, default='')
        dategroup.add_argument('--date', '-d', type=str, required=False, default='')

        # no arguments = 1 hour default
        result = self.library._uniform_time_parser(parser.parse_args([]))
        self.assertIn(result, _when(60*60))

        result = self.library._uniform_time_parser(parser.parse_args(['-t', 'sometime later']))
        self.assertEqual(result, 0)
        result = self.library._uniform_time_parser(parser.parse_args(['-d', 'manana']))
        self.assertEqual(result, 0)

        result = self.library._uniform_time_parser(parser.parse_args(['-t', 'now + 32min']))
        self.assertIn(result, _when(60*32))
        result = self.library._uniform_time_parser(parser.parse_args(['-t', 'now + 1 hour']))
        self.assertIn(result, _when(60*60*1))
        result = self.library._uniform_time_parser(parser.parse_args(['-t', 'now + 30days']))
        self.assertIn(result, _when(60*60*24*30))

        result = self.library._uniform_time_parser(parser.parse_args(['-d', ' + 25min ']))
        self.assertIn(result, _when(60*25))
        result = self.library._uniform_time_parser(parser.parse_args(['-d', '+1 hour']))
        self.assertIn(result, _when(60*60*1))
        result = self.library._uniform_time_parser(parser.parse_args(['-d', '+21d']))
        self.assertIn(result, _when(60*60*24*21))

    def test_ingest_config_file(self):
        ''' Test various scenarios for config files '''
        # No file at all
        self.assertEqual(self.library._ingest_config_file(None), {})
        # Some absent file
        self.assertEqual(self.library._ingest_config_file('/tmp/file-we-never-made'), {})
        # A file that's there but not parseable
        with open('/tmp/sillyfile.txt', 'w') as configfile:
            configfile.write('12345')
        self.assertEqual(self.library._ingest_config_file('/tmp/sillyfile.txt'), {})
        os.remove('/tmp/sillyfile.txt')
        # A file that's useable
        config = configparser.RawConfigParser()
        config.add_section('puppet')
        config.set('puppet', 'puppet_bin_path', '/opt/somepath')
        config.set('puppet', 'lastrunfile', '/opt/puppetlabs.yaml')
        config.set('puppet', 'agent_catalog_run_lockfile', '/opt/run.lck')
        config.add_section('puppetctl')
        config.set('puppetctl', 'state_file', '/home/status')
        with open('/tmp/modified.conf', 'w') as configfile:
            config.write(configfile)
        self.assertDictEqual(self.library._ingest_config_file('/tmp/modified.conf'),
                             {'puppet_bin_path': '/opt/somepath',
                              'lastrunfile': '/opt/puppetlabs.yaml',
                              'agent_catalog_run_lockfile': '/opt/run.lck',
                              'state_file': '/home/status'})
        os.remove('/tmp/modified.conf')
