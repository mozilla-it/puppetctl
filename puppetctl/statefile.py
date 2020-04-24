'''
    Script which controls puppet runs, allowing for temporary (never permanent)
    locking-out of puppet runs, or running in noop mode.
'''
import os
import copy
import re
import time
import hashlib
import shutil
import json

DEFAULT_STATE_FILE = '/var/lib/puppetctl.status'
BOGUS_STATE_FILE = '/tmp/broken-puppetctl.status'


class PuppetctlStatefile(object):
    '''
        Sample structure of the file for a singly-disabled host:
        {
            "868f437e": {
                "message": "",
                "locktype": "disabled",
                "time_begin": 1586450206,
                "time_begin_human": "Thu Apr  9 16:36:46 2020",
                "time_expiry": 1586453806,
                "time_expiry_human": "Thu Apr  9 17:36:46 2020",
                "user": "username"
            }
        }
    '''

    def __init__(self, state_file=None):
        ''' Init variables for PuppetctlStatefile '''
        self.defaults = {
            'state_file': DEFAULT_STATE_FILE,
        }
        if state_file is None:
            state_file = self.defaults.get('state_file')
        self.state_file = state_file
        self.bogus_state_file = BOGUS_STATE_FILE
        self.flag_state_disable = 'disable'
        self.flag_state_noop = 'nooperate'
        self.statefile_locktypes = [self.flag_state_disable, self.flag_state_noop]
        self.empty_state_file_contents = {}

    def _read_state_file(self, ):
        '''
            Private function.
            Perform a raw read of the state file with no embellishment.
            Do our best to return a usable structure, but if the file is
            crap then reset it to a known good state.
        '''
        if not os.path.isfile(self.state_file):
            self.reset_state_file()
            return copy.deepcopy(self.empty_state_file_contents)
        # at this point there is a state file.
        with open(self.state_file) as statefile_r:
            try:
                statefiledata_in = json.load(statefile_r)
            except ValueError:
                # We have managed to get unusable json into the state file.
                # The most likely scenario is that someone edited it by hand.
                # Try to take a backup of it in case we want to triage...
                try:
                    shutil.copyfile(self.state_file, self.bogus_state_file)
                except Exception:  # pragma: no cover  pylint: disable=locally-disabled,broad-except
                    # Deliberately catch any error from the copy, because this is
                    # a best-effort-only attempt to save the state file
                    pass
                # ... and then wipe the file and start over.
                self.reset_state_file()
                return copy.deepcopy(self.empty_state_file_contents)
        if not isinstance(statefiledata_in, dict):
            # Somehow the statefile isn't structured properly.  reset.
            self.reset_state_file()
            return copy.deepcopy(self.empty_state_file_contents)
        return copy.deepcopy(statefiledata_in)

    def read_state_file(self, ):
        '''
            Public function.
            Read the statefile, but massage it to where we don't report back
            on any expired locks.  Keep in mind that we may be reading the
            state file as a non-root user, so we end up doing double work,
            cleaning up expired locks on the thing we're going to report back,
            and also purging those same locks from the file (except that
            a write won't happen if we're not root).
        '''
        statefiledata_in = self._read_state_file()
        statefiledata_out = copy.deepcopy(statefiledata_in)
        for (lockid, lockitem) in statefiledata_in.items():
            if lockitem['time_expiry'] < time.time():
                # Remove it from the mem copy we're going to return...
                del statefiledata_out[lockid]
                # ... and from the disk copy (which we may not be
                # able to do for permissions reasons)
                self.remove_lock(lockid)
        return statefiledata_out

    @staticmethod
    def _allowed_to_write_statefile():  # pragma: no cover
        ''' Check if a user may write the statefile '''
        # This is a very simple function; we stomp it in mock testing, though.
        # In normal operations, we only want root to write to the state
        # file.  We're okay with nonroot doing reads for status-like
        # things.  Since a read operation can trigger cleanups, we could
        # end up with nonroot users being the first user on a clean box
        # and becoming owners of the statefile, or them failing to write
        # in the more general case.  So just return True to pretend like
        # we wrote a state file even if we didn't, because it doesn't
        # matter.  A nonroot is just going to get statuses which we'll
        # soft-filter.  The next root call can do the real writing.
        if os.geteuid() == 0:
            return True
        return False

    def write_state_file(self, json_obj):
        ''' Commit a blob to the state file.  Return True upon success. '''
        if not self._allowed_to_write_statefile():
            return False
        with open(self.state_file, 'w') as statefile_w:
            json.dump(json_obj, statefile_w, sort_keys=True, indent=4)
            statefile_w.write('\n')
        # This write could raise.
        return True

    def reset_state_file(self):
        ''' Wipe out the state file using our default setting '''
        try:
            return self.write_state_file(self.empty_state_file_contents)
        except IOError:
            return False

    def add_lock(self, user, locktype, expiry, message=''):
        '''
            Add a lock to the state file.  lockid if it commits, False if not
        '''
        if not re.match(r'^\w+$', user):
            raise ValueError('user must be an alphanumeric string')
        if not locktype in self.statefile_locktypes:
            raise ValueError('locktype was not valid')
        if not isinstance(expiry, int) or expiry <= int(time.time()):
            raise ValueError('expiry must epoch seconds in the future')
        if not isinstance(message, str):
            raise ValueError('message must be a string')
        if self._get_lock_ids(locktype, user):
            # one lock of a type per user.
            return False
        statefiledata_in = self.read_state_file()
        statefiledata_out = copy.deepcopy(statefiledata_in)
        lockitem = {
            'user': user,
            'locktype': locktype,
            'message': message,
            'time_expiry': int(expiry),
            # The human fields are not used AT ALL.  They exist so that if someone
            # reads the on-disk status file they get what's going on.  That's it.
            'time_expiry_human': time.ctime(int(expiry)),
            # time_begin and time_begin_human are added below
        }
        while True:
            # Now we're going to create a hash string to use as the key
            # WHAT the value is here doesn't matter.  Make sure we don't
            # create a dupe and cause a collision.
            now = time.time()
            lockitem['time_begin'] = int(now)
            lockitem['time_begin_human'] = time.ctime(int(now))
            _junk_str = str(lockitem)
            md5obj = hashlib.md5()
            md5obj.update(_junk_str.encode('utf-8'))
            hashstr = md5obj.hexdigest()[:8]
            if hashstr not in statefiledata_out:
                break
        statefiledata_out[hashstr] = lockitem
        if self.write_state_file(statefiledata_out):
            return hashstr
        return False

    def remove_lock(self, lockids):
        ''' Remove one-or-many locks from the state file '''
        statefiledata_in = self._read_state_file()
        statefiledata_out = copy.deepcopy(statefiledata_in)
        if not isinstance(lockids, list):
            lockids = [lockids]
        for lockid in lockids:
            del statefiledata_out[lockid]
        return self.write_state_file(statefiledata_out)

    def get_disable_lock_ids(self, user=None):
        ''' Wrapper to list disable locks '''
        return self._get_lock_ids(self.flag_state_disable, user)

    def get_noop_lock_ids(self, user=None):
        ''' Wrapper to list noop locks '''
        return self._get_lock_ids(self.flag_state_noop, user)

    def _get_lock_ids(self, locktype, user=None):
        '''
            Get the locks of a particular type, and if there's a user, also limit by that user.
        '''
        statefiledata_in = self.read_state_file()
        statefiledata_out = copy.deepcopy(statefiledata_in)
        for (lockid, _lockitem) in statefiledata_in.items():
            if statefiledata_in[lockid]['locktype'] != locktype:
                del statefiledata_out[lockid]
                continue
            if user is not None and statefiledata_in[lockid]['user'] != user:
                del statefiledata_out[lockid]
        output = sorted(list(statefiledata_out.keys()),
                        key=lambda x: statefiledata_out[x]['time_expiry'])
        return output

    def get_lock_info(self, lockid):
        ''' Get information about a lock from the state file '''
        statefiledata_in = self.read_state_file()
        lock = statefiledata_in.get(lockid, None)
        if lock is None:
            return ''
        if lock['locktype'] == self.flag_state_disable:
            tstr1 = 'Puppet has been disabled by {user} at {begintime} until {endtime}{message}'
        elif lock['locktype'] == self.flag_state_noop:
            tstr1 = 'Puppet is in nooperate mode by {user} at {begintime} until {endtime}{message}'

        tstr2 = ' with the following message: {}'.format(lock['message']) if lock['message'] else ''
        outputstring = tstr1.format(user=lock['user'],
                                    begintime=time.ctime(lock['time_begin']),
                                    endtime=time.ctime(lock['time_expiry']),
                                    message=tstr2,)
        return outputstring
