'''
    Perform the actual puppetctl-related tasks, as requested based
    on calls from the CLIHandler class.
'''
import sys
import os
import time
import subprocess
import signal
import syslog
from .statefile import PuppetctlStatefile

DEFAULT_PUPPET_BIN_PATH = '/opt/puppetlabs/puppet/bin'
DEFAULT_LASTRUNFILE = '/opt/puppetlabs/puppet/cache/state/last_run_summary.yaml'
DEFAULT_AGENT_CATALOG_RUN_LOCKFILE = '/opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock'


class PuppetctlExecution(object):
    ''' This class performs the tasks related to puppetctl '''

    def __init__(self, state_file=None,
                 puppet_bin_path=None,
                 lastrunfile=None,
                 agent_catalog_run_lockfile=None):
        ''' Set basic parameters for executing '''
        self.defaults = {
            'puppet_bin_path': DEFAULT_PUPPET_BIN_PATH,
            'lastrunfile': DEFAULT_LASTRUNFILE,
            'agent_catalog_run_lockfile': DEFAULT_AGENT_CATALOG_RUN_LOCKFILE,
        }
        # don't check state_file, it's not ours to manage.  pass it along.
        if puppet_bin_path is None:
            puppet_bin_path = self.defaults.get('puppet_bin_path')
        if lastrunfile is None:
            lastrunfile = self.defaults.get('lastrunfile')
        if agent_catalog_run_lockfile is None:
            agent_catalog_run_lockfile = self.defaults.get('agent_catalog_run_lockfile')
        pathitems = puppet_bin_path.split(':')
        for added_path in ['/bin', '/usr/bin']:
            if added_path not in pathitems:
                pathitems.append(added_path)
        self.puppet_bin_path = ':'.join(pathitems)
        self.lastrunfile = lastrunfile
        self.agent_catalog_run_lockfile = agent_catalog_run_lockfile
        sudo_user = os.getenv('SUDO_USER')
        user = os.getenv('USER')
        if sudo_user:
            self.invoking_user = sudo_user
        elif user:
            # This begins a somewhat sketchy path.  Someone is not sudo'ed.
            # This means they're either themselves and running a non-lock command (don't care),
            # OR, they're full root, i.e `sudo su -` rather than `sudo su` or `sudo -i`.  We have
            # no idea who they are besides 'root'.  The lock they create will be owned by root,
            # which introduces edge cases where someone coming through later and sudoing will 'be'
            # root, but yet not have access to root's locks because we can trace back who they are
            # and determine a real user.  This leads to "but I -am- root!" user confusion when
            # the user performs some commands as full root, and then a (same or different) user
            # tries to remove root's locks.
            #
            # We will treat creating the locks as "we will do what you say" and not really change
            # things, because we want to err on the side of disabling puppet quickly and safely.
            # The reenabling/removing of locks will be more cautious and require the user to jump
            # hoops when they hit these edge cases, because ultimately the users should be acting
            # as root in a consistent manner, and we are willing to penalize them a bit when they
            # do inconsistent things.
            #
            # tl;dr: use `sudo -i` and not `sudo su -` for the general case.
            self.invoking_user = user
        else:
            self.invoking_user = 'UNKNOWN'
        self.logging_tag = 'puppetctl[{}]'.format(self.invoking_user)
        self.statefile_object = PuppetctlStatefile(state_file)

    @staticmethod
    # This is a very simple function; we stomp it in mock testing, and since
    # it's about your userid, it's mostly untestable, so exeempted from coverage.
    def _allowed_to_run_command():  # pragma: no cover
        ''' Check if a command is allowed to be run. '''
        if os.geteuid() == 0:
            return True
        return False

    def log(self, message):
        ''' Log a line to syslog '''
        syslog.openlog(self.logging_tag)
        syslog.syslog(message)

    def log_print(self, message, color=None):
        ''' log a line to syslog AND print it out. '''
        self.log(message)
        self.color_print(message, color)

    @staticmethod
    def color_print(message, color=None):
        ''' print out a line with optional color '''
        if color and sys.stdout.isatty():
            print('\033[{color}m{message}\033[0m'.format(
                color=color,
                message=message))
        elif sys.stdout.isatty():
            print(message)
        else:
            print('puppetctl: {}'.format(message))

    def error_print(self, message, color=None):
        ''' Print a line and terminate with an error exit code. '''
        self.log_print(message, color)
        sys.exit(2)

    def is_enabled(self, user=None):
        '''
            If no user, return True/False on whether any disabler locks exist on the system.
            If user, return True/False on whether any disabler locks exist by/for that user.
        '''
        return len(self.statefile_object.get_disable_lock_ids(user)) == 0

    def is_operating(self, user=None):
        '''
            If no user, return True/False on whether any noop locks exist on the system.
            If user, return True/False on whether any noop locks exist by/for that user.
        '''
        return len(self.statefile_object.get_noop_lock_ids(user)) == 0

    def run(self, puppet_agent_args):
        ''' Run puppet.  Duh. '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run puppet.")
        if not self.is_enabled():
            # We don't want to run.  If this is a cron-kicked run, we'll just quietly exit.
            # If it's a human, tell them why not:
            if sys.stdout.isatty():
                self.lock_status()
            sys.exit(0)

        puppet_agent_options = ['--verbose', '--onetime', '--no-daemonize', '--no-splay']
        # beware of thundering-herds since we do a --no-splay
        if not self.is_operating():
            puppet_agent_options.append('--noop')
        puppet_agent_options.extend(puppet_agent_args)

        # In case someone has disabled with puppet instead of puppetctl:
        p_enable = subprocess.Popen(['puppet', 'agent', '--enable'],
                                    env={'PATH': self.puppet_bin_path})
        p_enable.wait()
        # Time to run puppet for real.  exec so we relenquish control:
        passed_args = ['puppet', 'agent'] + puppet_agent_options
        os.environ['PATH'] = self.puppet_bin_path
        os.execvpe('puppet', passed_args, env=os.environ)

    def enable(self):
        '''
            'enable' takes you out of 'disabled' mode.
            If you are in noop mode, it does not change anything, as you are
            already enabled.  DOES NOT break other people's locks
        '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'enable'.")
        my_disables = self.statefile_object.get_disable_lock_ids(self.invoking_user)
        my_noops = self.statefile_object.get_noop_lock_ids(self.invoking_user)
        if my_disables:
            if not self.statefile_object.remove_lock(my_disables):
                self.error_print(('Unable to remove prior disable lock '
                                  'before adding new one.'), '1;31')
            self.log_print("Puppet has been enabled.")
        elif my_noops:
            self.color_print(('Puppet is enabled, but is in nooperate mode.  '
                              "(hint: 'puppetctl operate' to change this)"))
        else:
            others_disables = self.statefile_object.get_disable_lock_ids()
            others_noops = self.statefile_object.get_noop_lock_ids()
            if others_disables:
                root_disables = self.statefile_object.get_disable_lock_ids('root')
                if others_disables == root_disables:
                    self.color_print(('Puppet is already enabled for {you}, but root has '
                                      'puppet disabled.').format(you=self.invoking_user))
                    self.color_print(('This is an odd state caused by someone disabling puppet '
                                      'from a login root shell.'))
                    self.color_print('If this is your lock, `sudo su -` and run an enable.')
                else:
                    self.color_print(("Puppet is already enabled for {you}, but other users have "
                                      "puppet disabled.").format(you=self.invoking_user))
                self.lock_status()
            elif others_noops:
                self.color_print(("Puppet is already enabled for {you}, but other users have "
                                  "puppet in noop mode.").format(you=self.invoking_user))
                self.lock_status()
            else:
                self.color_print("Puppet is already enabled.")

    def disable(self, force, expiry, message):
        '''
            Add a disable lock for this host.  In basic terms it's "stop puppet from running
            on this host."  This creates a lock for you.  Other people may have noop or
            disable locks of their own.
        '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'disable'.")
        my_disables = self.statefile_object.get_disable_lock_ids(self.invoking_user)
        my_noops = self.statefile_object.get_noop_lock_ids(self.invoking_user)
        if my_disables:
            if force:
                if not self.statefile_object.remove_lock(my_disables):
                    self.error_print(('Unable to remove prior disable lock '
                                      'before adding new one.'), '1;31')
                # fallthrough
            else:
                self.color_print('Puppet is already disabled.  (Add -f to override)')
                self.lock_status()
                sys.exit(1)
        if my_noops:
            # If we were in NOOP mode, disable is more important
            # abort out of noop mode and go into lockdown.
            if not self.statefile_object.remove_lock(my_noops):
                self.error_print(('Unable to remove prior noop lock '
                                  'before adding new one.'), '1;31')
            # fallthrough
        add = self.statefile_object.add_lock(user=self.invoking_user,
                                             locktype=self.statefile_object.flag_state_disable,
                                             expiry=expiry, message=message)
        if add:
            self.log_print(self.statefile_object.get_lock_info(add), '1;31')
            # We added a lock, but that's not the same as our previous behavior, where we
            # would only disable a host if puppet wasn't running...
            pidmap = self._puppet_processes_running()
            if pidmap:
                proc = "A 'puppet agent' process is" if (len(pidmap) == 1) \
                    else "Multiple 'puppet agent' processes are"
                self.color_print('{proc} running:'.format(proc=proc), '0;36')
                for (pidstr, cmd) in pidmap.items():
                    self.color_print('  {pid}  {cmd}'.format(pid=pidstr, cmd=cmd), '0;36')
                self.color_print('If you need to stop an active puppet run from finishing:', '0;33')
                self.color_print('   puppetctl panic-stop --force', '0;33')
        else:
            self.error_print('Unable to add lock.  Refusing to disable puppet.', '1;31')

    def operate(self):
        '''
            Takes the server out of 'nooperate' mode .
            If you are disabled mode, it does not change anything,
            as 'disable' outranks 'operate'
        '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'operate'.")
        my_disables = self.statefile_object.get_disable_lock_ids(self.invoking_user)
        my_noops = self.statefile_object.get_noop_lock_ids(self.invoking_user)
        if my_disables:
            self.color_print(('Puppet is disabled  '
                              "(hint: 'puppetctl enable' to change this)"))
        elif my_noops:
            if not self.statefile_object.remove_lock(my_noops):
                self.error_print(('Unable to remove prior noop lock '
                                  'before adding new one.'), '1;31')
            self.log_print("Puppet is back in 'operate' mode.")
        else:
            others_disables = self.statefile_object.get_disable_lock_ids()
            others_noops = self.statefile_object.get_noop_lock_ids()
            if others_disables:
                self.color_print(("Puppet is already in 'operate' mode for {you}, but other users "
                                  "have puppet disabled.").format(you=self.invoking_user))
                self.lock_status()
            elif others_noops:
                root_noops = self.statefile_object.get_noop_lock_ids('root')
                if others_noops == root_noops:
                    self.color_print(("Puppet is already in 'operate' mode for {you}, but root has "
                                      'puppet in noop mode.').format(you=self.invoking_user))
                    self.color_print(("This is an odd state caused by someone noop'ing puppet "
                                      'from a login root shell.'))
                    self.color_print('If this is your lock, `sudo su -` and run an operate.')
                else:
                    self.color_print(("Puppet is already in 'operate' mode for {you}, "
                                      'but other users have puppet in noop mode.').format(
                                          you=self.invoking_user))
                self.lock_status()
            else:
                self.color_print("Puppet is already in 'operate' mode.")


    def nooperate(self, force, expiry, message):
        '''
            Add a nooperate lock for this host.  In basic terms it's "let puppet run,
            but only in noop mode."  But it only creates YOUR lock.  Other people may
            have a lock, including a more comprehensive disabling lock.
        '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'nooperate'.")
        my_disables = self.statefile_object.get_disable_lock_ids(self.invoking_user)
        my_noops = self.statefile_object.get_noop_lock_ids(self.invoking_user)

        if my_disables:
            # Do not accept going into noop mode from a disabled state.  Force them to decide
            # to enable (since any enable can cause SOME changes to happen)
            self.color_print('Puppet is disabled. (You must be enabled to enter nooperate mode)')
            self.lock_status()
            sys.exit(2)

        if my_noops:
            if force:
                if not self.statefile_object.remove_lock(my_noops):
                    self.error_print(('Unable to remove prior noop lock '
                                      'before adding new one.'), '1;31')
                # fallthrough
            else:
                self.color_print('Puppet is already in nooperate mode.  (Add -f to override)')
                self.lock_status()
                sys.exit(1)
        add = self.statefile_object.add_lock(user=self.invoking_user,
                                             locktype=self.statefile_object.flag_state_noop,
                                             expiry=expiry, message=message)
        if add:
            self.log_print(self.statefile_object.get_lock_info(add), '1;31')
            # We added a lock, but that's not the same as our previous behavior, where we
            # would only disable a host if puppet wasn't running...
            pidmap = self._puppet_processes_running()
            if pidmap:
                proc = "A 'puppet agent' process is" if (len(pidmap) == 1) \
                    else "Multiple 'puppet agent' processes are"
                self.color_print('{proc} running:'.format(proc=proc), '0;36')
                for (pidstr, cmd) in pidmap.items():
                    self.color_print('  {pid}  {cmd}'.format(pid=pidstr, cmd=cmd), '0;36')
                self.color_print('If you need to stop an active puppet run from finishing:', '0;33')
                self.color_print('   puppetctl panic-stop --force', '0;33')
        else:
            self.error_print('Unable to add lock.  Refusing to noop puppet.', '1;31')

    def break_all_locks(self, force):
        '''
            'break_all_locks' will remove all locks that you-or-others have added.
            'force' is a counter and must be 2 or more - this is a drastic action
            and our solution is to require 'double force'.
        '''
        if self.is_enabled() and self.is_operating():
            self.color_print("There are no locks that need breaking.")
            sys.exit(0)
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'break-all-locks'.")
        if force < 2:
            self.error_print("Must use double --force to break all locks.")
        self.color_print(("Please consider the impact that overriding others' locks / reenabling "
                          "puppet may have on other peoples' work."))
        self.color_print('Breaking all locks (for you and anyone else) on this host in 10 seconds.')
        self.color_print('Press Ctrl-C to abort...')
        try:
            time.sleep(10)
        except (KeyboardInterrupt):  # pragma: no cover
            self.color_print('Exiting without breaking locks.')
            sys.exit(0)
        if self.statefile_object.reset_state_file():
            self.lock_status()
        else:
            self.error_print('Unable to break locks.  Please consult with a puppet admin.')

    def _puppet_processes_running(self, agent_catalog_run_lockfile=None):
        """
          Get the pid+cmdline for an actively running puppet agent, if any.

          Detecting puppet runs, without a human, is not simple.  The basic plan
          of 'just grep for it' can be problematic.  It is entirely valid to have
          a ps|grep return:

          pid1 puppet agent --verbose --onetime --no-daemonize --no-splay
          pid2 puppet agent --enable
          pid3 grep --color=auto puppet

          Mistaken pickups of grep-itself are annoying but easy enough to avoid by grepping
          for 'puppet agent'.  But even then you want to make sure that it's an actual
          run, not some interactive-like command such as --enable or --disable, that
          could potentially confuse a grep.  But grepping out --enable/--disable might
          leave us exposed to some future cases we forget to list.  So what we really
          want to do is check the pid that puppet creates on an agent run:

          $ puppet config print agent_catalog_run_lockfile
          /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock

          Demonstrated with two shells and good timing:
          $ puppet agent --verbose --onetime --no-daemonize --no-splay
          $ ls /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock
          /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock
          $ cat /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock ; echo
          30365
          $ pgrep -f 'puppet agent'
          30365

          So the lock file agrees with the running process.  Cool.  BUT, bad things can happen:

          $ puppet agent --verbose --onetime --no-daemonize --no-splay &
          [1] 30954
          $ pgrep -f 'puppet agent'
          30954
          $ cat /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock ; echo
          30954
          $ kill -9 `cat /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock`
          [1]+  Killed                  puppet agent --verbose --onetime --no-daemonize --no-splay
          $ ps auxwww | grep 'puppet agent'
          $ cat /opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock ; echo
          30954

          So the presence of the lock or the presence of the puppet agent process isn't
          sufficient on their own.  Puppet, in lib/ruby/vendor_ruby/puppet/agent/locker.rb
          indicates the test for running is the inability to make a lock of your own.
          It's probably a good idea for us NOT to be making out own agent locks when we're
          not actually puppet, and there's no API to query on the agent side because there's
          no process sitting around to query.

          So we're into 'our best effort' here.  Together these three factors (presence
          of a lock, presence of a process, and the contents of the lock poining to the
          process) are a good guess.  It's possible that we'll miss a process that goes
          rogue and doesn't lock, but that feels like a puppet problem more than one of
          ours.  And it's entirely possible someone could want to gut this with a better
          implementation.  Oh well.

          Side note, the lock is buried in the root-only section of the puppet working
          area.  Since the point of this function is to advise people of puppet that is
          running while they have root privs and when they're doing (root-required)
          disable/nooperate operations, this all works out.
        """

        if agent_catalog_run_lockfile is None:
            agent_catalog_run_lockfile = self.agent_catalog_run_lockfile

        returnval = {}
        if os.geteuid() != 0:
            # We can't access the puppet lock if we're not root.
            return returnval
        try:
            # try to get the lock's contained value
            with open(agent_catalog_run_lockfile, 'r') as lockfile:
                pid_in_lock = lockfile.read()
        except IOError:  # proc has already terminated
            return returnval
        if not pid_in_lock.isdigit():
            # not a viable pid in the lock
            return returnval
        path = os.path.join('/proc', pid_in_lock, 'cmdline')
        try:
            pid_owner = os.stat(path).st_uid
        except OSError:  # proc has already terminated
            return returnval
        if pid_owner == 0:  # must be root-owned
            try:
                cmdline_argv = open(path, 'r').read().split('\0')
            except IOError:  # proc has already terminated
                return returnval
            # sample cmdline_argv = ['/opt/puppetlabs/puppet/bin/ruby',
            # '/opt/puppetlabs/puppet/bin/puppet', 'agent', '--verbose',
            # '--onetime', '--no-daemonize', '--no-splay', '']
            cmdline_as_string = ' '.join(cmdline_argv)
            if 'puppet agent' in cmdline_as_string:
                returnval[pid_in_lock] = cmdline_as_string
        return returnval

    def panic_stop(self, force=False, sleep_between_signals=2):
        '''
            'panic_stop' will stop an active puppet run.
        '''
        if not self._allowed_to_run_command():
            self.error_print("Must be root to run 'panic-stop'.")
        pidmap = self._puppet_processes_running()
        if not pidmap:
            self.log_print("No running 'puppet agent' found.")
            sys.exit(0)
        # While there should only ever be one agent running, treat it as
        # potentially multiple, just in case we ever expand.
        for (pidstr, cmd) in pidmap.items():
            self.color_print("Sending SIGTERM to pid {pid} / '{cmd}'".format(pid=pidstr, cmd=cmd))
            os.kill(int(pidstr), signal.SIGTERM)
        if not force:
            time.sleep(sleep_between_signals)

        # Rerun the pid check since time has passed.
        pidmap = self._puppet_processes_running()
        # If we're lucky, things exited by now.  Otherwise, big hammer time.
        if not pidmap:
            self.log_print("No running 'puppet agent' found.")
            sys.exit(0)
        for (pidstr, cmd) in pidmap.items():
            self.color_print("Sending SIGKILL to pid {pid} / '{cmd}'".format(pid=pidstr, cmd=cmd))
            os.kill(int(pidstr), signal.SIGKILL)
        # One last time
        time.sleep(1)
        pidmap = self._puppet_processes_running()
        if not pidmap:
            self.log_print("No running 'puppet agent' found.")
            sys.exit(0)
        for (pidstr, cmd) in pidmap.items():
            self.log_print("pid {pid} / '{cmd}' did NOT die.".format(pid=pidstr, cmd=cmd))
        sys.exit(1)

    def _parse_puppet_lastrunfile(self, lastrunfile):
        '''
            This function is weird.  It uses ruby to parse the puppet yaml
            file.  This saves us from adding python's weird yaml module as a site-wide dependency.
        '''

        rubyscript_base = "output = File.open('" + lastrunfile + "'){ |data| YAML::load(data) }; "

        age_script = rubyscript_base + "puts output['time']['last_run'].to_i"
        errors_script = rubyscript_base + "puts output['resources']['failed']"
        config_script = rubyscript_base + "puts output['version']['config']"

        p_age = subprocess.Popen(['ruby', '-ryaml', '-e', age_script],
                                 env={'PATH': self.puppet_bin_path}, stdout=subprocess.PIPE)
        p_age.wait()
        age = p_age.communicate()[0].rstrip()
        p_errors = subprocess.Popen(['ruby', '-ryaml', '-e', errors_script],
                                    env={'PATH': self.puppet_bin_path}, stdout=subprocess.PIPE)
        p_errors.wait()
        errors = p_errors.communicate()[0].rstrip()
        p_config = subprocess.Popen(['ruby', '-ryaml', '-e', config_script],
                                    env={'PATH': self.puppet_bin_path}, stdout=subprocess.PIPE)
        p_config.wait()
        config = p_config.communicate()[0].rstrip().decode()
        now = int(time.time())
        return {'age': now-int(age), 'errors': int(errors), 'config': config}

    @staticmethod
    def dhms(secs_in):
        ''' from seconds, create a string that describes days/hours/minuts/seconds '''
        secs = int(secs_in)
        days = secs//86400
        hours = (secs - days*86400)//3600
        minutes = (secs - days*86400 - hours*3600)//60
        seconds = secs - days*86400 - hours*3600 - minutes*60
        result = ('{0}d '.format(days) if days else "") + \
                 ('{0}h '.format(hours) if hours else "") + \
                 ('{0}m '.format(minutes) if minutes else "") + \
                 ('{0}s '.format(seconds) if seconds else "")
        if result == '':
            result = '0s '
        return result.rstrip()

    def _status_of_puppet(self, lastrunfile):
        '''
            return a structure containing info about the last run of puppet
            (not about the locks in puppetctl)
        '''
        if os.geteuid() != 0:
            return {'errors': 0, 'message': ('Cannot provide the last run information '
                                             'on puppet without being root.')}
        if not os.path.exists(lastrunfile):
            msg = 'No "{}" file to get puppet information from.'.format(lastrunfile)
            return {'errors': 0, 'message': msg, }
        last_run_data = self._parse_puppet_lastrunfile(lastrunfile)
        msg_template = 'Puppet last ran {dhms} ago with {errors} errors, applied version {config}'
        return {
            'errors': last_run_data['errors'],
            'message': msg_template.format(dhms=self.dhms(last_run_data['age']),
                                           errors=last_run_data['errors'],
                                           config=last_run_data['config'])
        }

    def _status_of_puppetctl(self):
        '''
            return a structure about the lock status of puppetctl (not puppet)
        '''
        disable_locks = self.statefile_object.get_disable_lock_ids()
        disable_locks_data = [self.statefile_object.get_lock_info(x) for x in disable_locks]
        nooperate_locks = self.statefile_object.get_noop_lock_ids()
        nooperate_locks_data = [self.statefile_object.get_lock_info(x) for x in nooperate_locks]

        if disable_locks and nooperate_locks:
            color = '1;31'
        elif disable_locks and not nooperate_locks:
            color = '1;31'
        elif not disable_locks and nooperate_locks:
            color = '0;36'
        elif not disable_locks and not nooperate_locks:
            color = None

        if color is None:
            message = 'Puppet is enabled and in operating mode.'
        else:
            message = '\n'.join(disable_locks_data + nooperate_locks_data)
        return {'message': message, 'color': color,
                'disable': len(disable_locks), 'nooperate': len(nooperate_locks)}

    def status(self):
        '''
            Determine the state of puppet and puppetctl's locks independently,
            and give an exit code based on the state of puppet (not puppetctl)
        '''
        puppet_state = self._status_of_puppet(self.lastrunfile)
        puppetctl_state = self._status_of_puppetctl()
        self.color_print(puppet_state['message'], '0;33' if puppet_state['errors'] else None)
        self.color_print(puppetctl_state['message'], puppetctl_state['color'])
        # exit 0 if there are no errors, exit 1 if there were errors:
        sys.exit(1 if puppet_state['errors'] else 0)

    def lock_status(self):
        ''' Determine the state of puppetctl's locks.  Doesn't exit itself, but implies one. '''
        puppetctl_state = self._status_of_puppetctl()
        self.color_print(puppetctl_state['message'], puppetctl_state['color'])

    def motd_status(self):
        ''' Determine the state of puppetctl's locks.  Reports if there are locks. '''
        puppetctl_state = self._status_of_puppetctl()
        if puppetctl_state['disable'] != 0 or puppetctl_state['nooperate'] != 0:
            self.color_print(puppetctl_state['message'], puppetctl_state['color'])
        sys.exit(0)
