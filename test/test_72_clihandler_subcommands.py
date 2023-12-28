'''
    PuppetctlCLIHandler test script
'''

import unittest
import time
from io import StringIO
import test.context  # pylint: disable=unused-import
import mock
from puppetctl import PuppetctlExecution, PuppetctlCLIHandler


class TestCLIHandler(unittest.TestCase):
    ''' Class of tests about parsing the CLI inputs. '''

    def setUp(self):
        ''' Preparing test rig '''
        self.library = PuppetctlCLIHandler()

    def test_sc_is_enabled(self):
        ''' Check subcommand_is_enabled '''
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=True), \
                self.assertRaises(SystemExit) as isenabled:
            self.library.subcommand_is_enabled('puppetctl', 'is-enabled', [])
        self.assertEqual(isenabled.exception.code, 0)
        self.assertEqual('enabled\n', fake_out.getvalue())
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False), \
                self.assertRaises(SystemExit) as isenabled:
            self.library.subcommand_is_enabled('puppetctl', 'is-enabled', [])
        self.assertEqual(isenabled.exception.code, 1)
        self.assertEqual('disabled\n', fake_out.getvalue())

    def test_sc_is_operating(self):
        ''' Check subcommand_is_operating '''
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, 'is_operating', return_value=True), \
                self.assertRaises(SystemExit) as isoperating:
            self.library.subcommand_is_operating('puppetctl', 'is-operating', [])
        self.assertEqual(isoperating.exception.code, 0)
        self.assertEqual('operating\n', fake_out.getvalue())
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                mock.patch.object(PuppetctlExecution, 'is_operating', return_value=False), \
                self.assertRaises(SystemExit) as isoperating:
            self.library.subcommand_is_operating('puppetctl', 'is-operating', [])
        self.assertEqual(isoperating.exception.code, 1)
        self.assertEqual('nooperating\n', fake_out.getvalue())

    def test_sc_enable(self):
        ''' Check subcommand_enable '''
        with mock.patch.object(PuppetctlExecution, 'enable') as mock_enable:
            self.library.subcommand_enable('puppetctl', 'enable', [])
        mock_enable.assert_called_once_with()
        # help is allowed:
        with mock.patch('sys.stdout', new=StringIO()), \
                self.assertRaises(SystemExit) as exit_help:
            self.library.subcommand_enable('puppetctl', 'enable', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # no other args are:
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as exit_help:
            self.library.subcommand_enable('puppetctl', 'enable', ['--anythingelse'])
        self.assertEqual(exit_help.exception.code, 2)

    def test_sc_disable(self):
        ''' Check subcommand_disable '''
        # help is allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_disable('puppetctl', 'disable', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # try some disables:
        with mock.patch.object(PuppetctlExecution, 'disable') as mock_disable:
            self.library.subcommand_disable('puppetctl', 'disable', [])
        mock_disable.assert_called_once_with(force=False,
                                             expiry=int(time.time())+60*60,
                                             message='')
        with mock.patch.object(PuppetctlExecution, 'disable') as mock_disable:
            self.library.subcommand_disable('puppetctl', 'disable', ['--force'])
        mock_disable.assert_called_once_with(force=True,
                                             expiry=int(time.time())+60*60,
                                             message='')
        with mock.patch.object(PuppetctlExecution, 'disable') as mock_disable:
            self.library.subcommand_disable('puppetctl', 'disable', ['-t', 'now+2h'])
        mock_disable.assert_called_once_with(force=False,
                                             expiry=int(time.time())+60*60*2,
                                             message='')
        with mock.patch.object(PuppetctlExecution, 'disable') as mock_disable:
            self.library.subcommand_disable('puppetctl', 'disable', ['-d', '+3h'])
        mock_disable.assert_called_once_with(force=False,
                                             expiry=int(time.time())+60*60*3,
                                             message='')
        with mock.patch.object(PuppetctlExecution, 'disable') as mock_disable:
            self.library.subcommand_disable('puppetctl', 'disable', ['-m', 'I said so'])
        mock_disable.assert_called_once_with(force=False,
                                             expiry=int(time.time())+60*60,
                                             message='I said so')
        # garbage time is rejected
        with mock.patch('sys.stdout', new=StringIO()) as fake_out, \
                self.assertRaises(SystemExit) as exit_help:
            self.library.subcommand_disable('puppetctl', 'disable', ['-t', 'the future'])
        self.assertIn('Unparsable time string', fake_out.getvalue())
        self.assertEqual(exit_help.exception.code, 1)
        # no other args are allowed:
        with mock.patch('sys.stderr', new=StringIO()), \
                self.assertRaises(SystemExit) as exit_help:
            self.library.subcommand_disable('puppetctl', 'disable', ['--anythingelse'])
        self.assertEqual(exit_help.exception.code, 2)

    def test_sc_operate(self):
        ''' Check subcommand_operate '''
        with mock.patch.object(PuppetctlExecution, 'operate') as mock_operate:
            self.library.subcommand_operate('puppetctl', 'operate', [])
        mock_operate.assert_called_once_with()
        # help is allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_operate('puppetctl', 'operate', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # no other args are:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stderr', new=StringIO()):
            self.library.subcommand_operate('puppetctl', 'operate', ['--anythingelse'])
        self.assertEqual(exit_help.exception.code, 2)

    def test_sc_nooperate(self):
        ''' Check subcommand_nooperate '''
        # help is allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # try some nooperates:
        with mock.patch.object(PuppetctlExecution, 'nooperate') as mock_nooperate:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', [])
        mock_nooperate.assert_called_once_with(force=False,
                                               expiry=int(time.time())+60*60,
                                               message='')
        with mock.patch.object(PuppetctlExecution, 'nooperate') as mock_nooperate:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['--force'])
        mock_nooperate.assert_called_once_with(force=True,
                                               expiry=int(time.time())+60*60,
                                               message='')
        with mock.patch.object(PuppetctlExecution, 'nooperate') as mock_nooperate:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['-t', 'now+2h'])
        mock_nooperate.assert_called_once_with(force=False,
                                               expiry=int(time.time())+60*60*2,
                                               message='')
        with mock.patch.object(PuppetctlExecution, 'nooperate') as mock_nooperate:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['-d', '+3h'])
        mock_nooperate.assert_called_once_with(force=False,
                                               expiry=int(time.time())+60*60*3,
                                               message='')
        with mock.patch.object(PuppetctlExecution, 'nooperate') as mock_nooperate:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['-m', 'I said so'])
        mock_nooperate.assert_called_once_with(force=False,
                                               expiry=int(time.time())+60*60,
                                               message='I said so')
        # garbage time is rejected
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stdout', new=StringIO()) as fake_out:
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['-t', 'the future'])
        self.assertIn('Unparsable time string', fake_out.getvalue())
        self.assertEqual(exit_help.exception.code, 1)
        # no other args are allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stderr', new=StringIO()):
            self.library.subcommand_nooperate('puppetctl', 'nooperate', ['--anythingelse'])
        self.assertEqual(exit_help.exception.code, 2)

    def test_sc_run(self):
        ''' Check subcommand_run '''
        with mock.patch.object(PuppetctlExecution, 'run') as mock_run:
            self.library.subcommand_run('puppetctl', 'run', [])
        mock_run.assert_called_once_with([])
        # args passed along blindly:
        with mock.patch.object(PuppetctlExecution, 'run') as mock_run:
            self.library.subcommand_run('puppetctl', 'run', ['--test'])
        mock_run.assert_called_once_with(['--test'])

    def test_sc_cronrun(self):
        ''' Check subcommand_cron_run '''
        with mock.patch.object(PuppetctlExecution, 'cron_run') as mock_run:
            self.library.subcommand_cron_run('puppetctl', 'cron-run', [])
        mock_run.assert_called_once_with([])
        # args passed along blindly:
        with mock.patch.object(PuppetctlExecution, 'cron_run') as mock_run:
            self.library.subcommand_cron_run('puppetctl', 'cron-run', ['--test'])
        mock_run.assert_called_once_with(['--test'])

    def test_sc_status(self):
        ''' Check subcommand_status '''
        with mock.patch.object(PuppetctlExecution, 'status') as mock_status:
            self.library.subcommand_status('puppetctl', 'status', [])
        mock_status.assert_called_once_with()
        # args discarded:
        with mock.patch.object(PuppetctlExecution, 'status') as mock_status:
            self.library.subcommand_status('puppetctl', 'status', ['--anyargs'])
        mock_status.assert_called_once_with()

    def test_sc_lock_status(self):
        ''' Check subcommand_lock_status '''
        with mock.patch.object(PuppetctlExecution, 'lock_status') as mock_status:
            self.library.subcommand_lock_status('puppetctl', 'lock-status', [])
        mock_status.assert_called_once_with()
        # args discarded:
        with mock.patch.object(PuppetctlExecution, 'lock_status') as mock_status:
            self.library.subcommand_lock_status('puppetctl', 'lock-status', ['--anyargs'])
        mock_status.assert_called_once_with()

    def test_sc_motd_status(self):
        ''' Check subcommand_motd_status '''
        with mock.patch.object(PuppetctlExecution, 'motd_status') as mock_status:
            self.library.subcommand_motd_status('puppetctl', 'motd-status', [])
        mock_status.assert_called_once_with()
        # args discarded:
        with mock.patch.object(PuppetctlExecution, 'motd_status') as mock_status:
            self.library.subcommand_motd_status('puppetctl', 'motd-status', ['--anyargs'])
        mock_status.assert_called_once_with()

    def test_sc_break_all_locks(self):
        ''' Check subcommand_break_all_locks '''
        # No arguments = insufficient force
        with mock.patch.object(PuppetctlExecution, 'break_all_locks') as mock_break, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_break_all_locks('puppetctl', 'break-all-locks', [])
        mock_break.assert_called_once_with(0)
        # help is allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch.object(PuppetctlExecution, 'is_enabled', return_value=False), \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_break_all_locks('puppetctl', 'break-all-locks', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # insufficient force:
        with mock.patch.object(PuppetctlExecution, 'break_all_locks') as mock_break, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_break_all_locks('puppetctl', 'break-all-locks', ['--force'])
        mock_break.assert_called_once_with(1)
        # sufficient force:
        with mock.patch.object(PuppetctlExecution, 'break_all_locks') as mock_break, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_break_all_locks('puppetctl', 'break-all-locks',
                                                    ['--force', '--force'])
        mock_break.assert_called_once_with(2)

    def test_sc_panic_stop(self):
        ''' Check subcommand_panic_stop '''
        # No arguments = run:
        with mock.patch.object(PuppetctlExecution, 'panic_stop') as mock_break:
            self.library.subcommand_panic_stop('puppetctl', 'panic-stop', [])
        mock_break.assert_called_once_with(False)
        # help is allowed:
        with self.assertRaises(SystemExit) as exit_help, \
                mock.patch('sys.stdout', new=StringIO()):
            self.library.subcommand_panic_stop('puppetctl', 'panic-stop', ['--help'])
        self.assertEqual(exit_help.exception.code, 0)
        # sufficient force:
        with mock.patch.object(PuppetctlExecution, 'panic_stop') as mock_break:
            self.library.subcommand_panic_stop('puppetctl', 'panic-stop', ['--force'])
        mock_break.assert_called_once_with(True)
