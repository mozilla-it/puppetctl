'''
    Handle the user-supplied argument parsing for puppetctl
'''
import sys
import re
import time
import argparse
try:
    import configparser
except ImportError:  # pragma: no cover
    from six.moves import configparser
import textwrap
from .execution import PuppetctlExecution


class PuppetctlCLIHandler(object):
    '''
    This class parses the CLI arguments for the subclasses and turns them into
    parameters that we can pass over to the Execution class for performing the
    actual work.
    '''

    def __init__(self):
        ''' Spin up our executing object '''
        # Creates an object with defaults.  It's possible we'll stomp on this in main after we
        # read in a conf file, but for consistency's sake we create the exec object at this
        # point.  The inits do very little and so this is cheap, and it REALLY makes testing
        # easier if this variable can't be None for a while.
        self.runner = PuppetctlExecution()

    @staticmethod
    def _ingest_config_file(cfilename):
        ''' Given a config file pointer, read out the parameters we care about. '''
        acceptable_options = {
            'puppet': ['puppet_bin_path', 'lastrunfile', 'agent_catalog_run_lockfile'],
            'puppetctl': ['state_file'],
        }
        returndict = {}
        if cfilename:
            cfileparser = configparser.ConfigParser()
            try:
                cfileparser.read(cfilename)
            except configparser.MissingSectionHeaderError:
                return returndict
            for (section, options) in acceptable_options.items():
                for option in options:
                    try:
                        returndict[option] = cfileparser.get(section, option)
                    except (configparser.MissingSectionHeaderError,
                            configparser.NoSectionError,
                            configparser.NoOptionError):
                        pass
        return returndict

    def main(self, argv):
        ''' Spin up the main argument parser, hand off to subcommand methods '''
        main_command = argv[0]
        # We create our own description and usage here, because the dual parsers below will each
        # have an incomplete picture of the desired behavior for the user.
        usage = '%(prog)s [--config conffile] command'
        description = textwrap.dedent('''\
            Routine commands, anyone may run:
               is-enabled       True if puppet is enabled
               is-operating     True if puppet is in normal (not noop) mode
               status           Status of the latest puppet run, and puppetctl
               lock-status      Status of puppetctl
               motd-status      Status of puppetctl (quiet if there are no locks)
            Routine commands, requires root:
               enable           Enable puppet runs
               disable          Disable future puppet runs
               operate          Have puppet operate in normal mode
               nooperate        Have puppet operate in noop mode
               run              Puppet agent run
            Emergency commands, requires root:
               break-all-locks  Removes all locks, even ones that do not belong to you
               panic-stop       Kills any active puppet run, disables puppet for one hour''')

        # Create a parser whose only job is to grab --config:
        conf_only_parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=description,
            usage=usage,
            # suppress help here - the other parser will provide it.
            add_help=False
        )
        conf_only_parser.add_argument('--config', action='store', required=False,
                                      metavar='conffile', default='/etc/puppetctl.conf',
                                      help='path to puppetctl.conf config file')
        # Create a parser that does all the work for the subcommands:
        parser = argparse.ArgumentParser(description=description, usage=usage,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('command', help='puppetctl command to run',
                            choices=['help', 'is-enabled', 'is-operating', 'enable', 'disable',
                                     'operate', 'nooperate', 'run', 'status', 'lock-status',
                                     'motd-status', 'break-all-locks', 'panic-stop'])
        # If we got nothing but argv[0] then bail out:
        if len(argv) < 2:
            parser.print_help()
            sys.exit(1)
        # At this point we have SOMETHING args, so parse what we can.
        # CAUTION, at this point we will gobble --config if it appears anywhere.
        # This prevents any future subcommand from using --config, but that's not
        # likely to be a problem for us.
        confargs, post_conf_args = conf_only_parser.parse_known_args(argv[1:])
        # ^ This captures --config if it exists, and everything else is in
        # post_conf_args.  Now, run the first thing in post_conf_args through
        # the next parser, looking for a subcommand
        args = parser.parse_args(post_conf_args[0:1])
        entered_subcommand = args.command
        if entered_subcommand == 'help':
            parser.print_help()
            sys.exit(0)
        _flattened_subcommand = re.sub(r'-', '_', entered_subcommand)
        subcommand_methodname = 'subcommand_{}'.format(_flattened_subcommand)
        if not hasattr(self, subcommand_methodname):  # pragma: no cover
            # This is a safety valve we should never reach, as it would mean
            # we added something to 'choices' without making a function for it.
            print('Unrecognized command "{}"\n'.format(entered_subcommand))
            parser.print_help()
            sys.exit(1)
        if confargs.config:
            configdict = self._ingest_config_file(confargs.config)
            self.runner = PuppetctlExecution(**configdict)
        # use dispatch pattern to invoke method with same name
        getattr(self, subcommand_methodname)(main_command, entered_subcommand, post_conf_args[1:])

    def subcommand_is_enabled(self, _ctlcmd, _subcmd, _argv):
        ''' Check if puppet is allowed to run.  Callable by nonroot. '''
        # we eat the argv unparsed because we neither want nor accept args.
        if self.runner.is_enabled():
            print('enabled')
            sys.exit(0)
        else:
            print('disabled')
            sys.exit(1)

    def subcommand_is_operating(self, _ctlcmd, _subcmd, _argv):
        ''' Check if puppet is in noop mode.  Callable by nonroot. '''
        # we eat the argv unparsed because we neither want nor accept args.
        if self.runner.is_operating():
            print('operating')
            sys.exit(0)
        else:
            print('nooperating')
            sys.exit(1)

    @staticmethod
    def _uniform_time_parser(parser):
        '''
            This is the time parser used by disable and nooperate.
            It is very basic and may need expanding depending on user feedback.
        '''
        dhms_multiplier = {
            'y': 60*60*24*365,
            'd': 60*60*24,
            'h': 60*60,
            'm': 60,
            's': 1,
        }
        at_time_string = getattr(parser, 'time', None)
        date_time_string = getattr(parser, 'date', None)
        if not at_time_string and not date_time_string:
            at_time_string = 'now + 1 hour'
        if at_time_string:
            # this used to be the place where we would just lightly massage
            # the datestrings and pass them to 'at'.  Since we have removed
            # 'at' we are doing a minimal parsing to simulate the most
            # common cases people use, and we can expand this as needed.
            #
            # The most common, and thus assumed, pattern is 'now + N hours'
            #
            pattern = re.compile(r"""^     # start of string
                                     \s*   # any leading spaces
                                     now   # the literal word now
                                     \s*   # any spaces
                                     \+    # literal plus sign
                                     \s*   # any spaces
                                     (\d+) # some digits
                                     \s*   # any spaces
                                     (y|yr|yrs|year|years|d|day|days|h|hr|hrs|hour|hours|  # time
                                      m|min|mins|minute|minutes|s|sec|secs|second|seconds) # units
                                     \s*   # any spaces
                                     $     # end of string
                                 """, re.VERBOSE)
            #
            # This is somewhat limiting but it works for our base case.
            #
            result = pattern.search(at_time_string)
            if result is None:
                return 0
            timenum = int(result.group(1))
            raw_unit = result.group(2)
            unit = raw_unit[0:1]   # truncate down to one letter, ydhms
            expirytime = int(time.time()) + dhms_multiplier.get(unit) * timenum
            return expirytime
        if date_time_string:
            pattern = re.compile(r"""^     # start of string
                                     \s*   # any leading spaces
                                     \+    # literal plus sign
                                     \s*   # any spaces
                                     (\d+) # some digits
                                     \s*   # any spaces
                                     (y|yr|yrs|year|years|d|day|days|h|hr|hrs|hour|hours|  # time
                                      m|min|mins|minute|minutes|s|sec|secs|second|seconds) # units
                                     \s*   # any spaces
                                     $     # end of string
                                 """, re.VERBOSE)
            result = pattern.search(date_time_string)
            if result is None:
                return 0
            timenum = int(result.group(1))
            raw_unit = result.group(2)
            unit = raw_unit[0:1]   # truncate down to one letter, dhms
            expirytime = int(time.time()) + dhms_multiplier.get(unit) * timenum
            return expirytime
        # unreachable, but leaving this in to help linting on consistent return values
        return 0  # pragma: no cover

    def subcommand_enable(self, ctlcmd, subcmd, argv):
        ''' Remove a disable lock, if possible '''
        # no arguments, but catch help
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         description='Enable future puppet runs')
        parser.parse_args(argv)
        self.runner.enable()

    def subcommand_disable(self, ctlcmd, subcmd, argv):
        ''' Add a disable lock, if allowed '''
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         description='Disable future puppet runs')
        parser.add_argument('--force', '-f', action='store_true',
                            help=('Force disable: overrides an existing disable with our new '
                                  'time limit.  If puppet is running it gets terminated.'))
        parser.add_argument('--message', '-m', type=str, required=False, metavar='message',
                            default='',
                            help='message that will be displayed when status is queried')
        dategroup = parser.add_mutually_exclusive_group()
        dategroup.add_argument('--time', '-t', type=str, required=False,
                               metavar='at(1) timestring', default='',
                               help='''Set the disable expiration time using at(1) format
 Example: 'now + 2 hours' ''')
        dategroup.add_argument('--date', '-d', type=str, required=False,
                               metavar='+__h timestring', default='',
                               help='''Set the disable expiration time using short formats
 Duration: +__m, +__h, +__d (minutes, hours, days from now)''')

        args = parser.parse_args(argv)
        expiry = self._uniform_time_parser(args)
        if expiry < int(time.time()):
            print('Unparsable time string provided.  If '
                  'you think it should be, please file a bug.')
            parser.print_usage()
            sys.exit(1)
        self.runner.disable(force=args.force, expiry=expiry, message=args.message)

    def subcommand_operate(self, ctlcmd, subcmd, argv):
        ''' Remove noop lock, if present. '''
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         description='Bring puppetctl out of noop mode')
        parser.parse_args(argv)
        self.runner.operate()

    def subcommand_nooperate(self, ctlcmd, subcmd, argv):
        ''' Add a noop lock, if possible '''
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         description='Put future puppet runs in noop mode')
        parser.add_argument('--force', '-f', action='store_true',
                            help=('Force nooperate: overrides an existing '
                                  'nooperate with our new time limit'))
        parser.add_argument('--message', '-m', type=str, required=False,
                            metavar='message', default='',
                            help='message that will be displayed when status is queried')
        dategroup = parser.add_mutually_exclusive_group()
        dategroup.add_argument('--time', '-t', type=str, required=False, metavar='at(1) timestring',
                               default='',
                               help='''Set the nooperate expiration time using at(1) format
 Example: 'now + 2 hours' ''')
        dategroup.add_argument('--date', '-d', type=str, required=False, metavar='+__h timestring',
                               default='',
                               help='''Set the nooperate expiration time using short formats
 Duration: +__m, +__h, +__d (minutes, hours, days from now)''')

        args = parser.parse_args(argv)
        expiry = self._uniform_time_parser(args)
        if expiry < int(time.time()):
            print('Unparsable time string provided.  If you think it should be, please file a bug.')
            parser.print_usage()
            sys.exit(1)
        self.runner.nooperate(force=args.force, expiry=expiry, message=args.message)

    def subcommand_run(self, _ctlcmd, _subcmd, argv):
        ''' Tell puppet to run.  Pass along all arguments as params to puppet agent. '''
        self.runner.run(argv)

    def subcommand_status(self, _ctlcmd, _subcmd, _argv):
        '''
            Provide a human-readable form of the state of both puppet and the
            locks that puppetctl has set
        '''
        self.runner.status()

    def subcommand_lock_status(self, _ctlcmd, _subcmd, _argv):
        ''' Provide a human-readable form of the puppetctl lock state '''
        self.runner.lock_status()

    def subcommand_motd_status(self, _ctlcmd, _subcmd, _argv):
        ''' Provide a motd-ready form of the puppetctl lock state '''
        self.runner.motd_status()

    def subcommand_break_all_locks(self, ctlcmd, subcmd, argv):
        ''' Forcibly remove all locks on a host '''
        description = textwrap.dedent('''\
            Break all locks on a host.

            NOTE: You must provide TWO instances of --force in order to break all locks.

            It is highly recommended that you speak to the person who added a lock
            before you break someone else's lock and reenable puppet runs.''')
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         formatter_class=argparse.RawDescriptionHelpFormatter,
                                         description=description)
        parser.add_argument('--force', '-f', action='count', default=0,
                            help='force break locks (option must appear twice)')
        args = parser.parse_args(argv)
        # pass along the 'force' count, we'll check it on the other side
        self.runner.break_all_locks(args.force)

    def subcommand_panic_stop(self, ctlcmd, subcmd, argv):
        ''' Stop any active puppet run '''
        description = textwrap.dedent('''\
            If there is an active puppet run, this will stop it.
            We try with SIGTERM initially, and SIGKILL if it hasn't stopped in 2 seconds.''')
        parser = argparse.ArgumentParser(prog='{} {}'.format(ctlcmd, subcmd),
                                         formatter_class=argparse.RawDescriptionHelpFormatter,
                                         description=description)
        parser.add_argument('--force', '-f', action='store_true',
                            help='No delay - SIGTERM is immediately followed by SIGKILL')
        args = parser.parse_args(argv)
        self.runner.panic_stop(args.force)
