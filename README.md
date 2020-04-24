# puppetctl
puppetctl is a wrapper around puppet to aid in system administration changes.

Rather than using a daemonized agent and long strings of options, all runs go through `puppetctl run`.  Users may disable future runs of puppet for periods of time, or place the host in nooperate
 mode to test changes without worrying about puppet coming through and making a change.

## Available Subcommands:
### Status-Related Commands

Status commands do not require root.

* **is-enabled**
* **is-operating**
These are systemd-like requests to find out if puppet is enabled (not disabled) or operating (not in noop mode).  Returns the usual bash-style 0=true, 1=false as well as a human-readable response
* **status**
Tells you the status of the last puppet run (if you are root).  Also tells you the lock-status.
* **lock-status**
Tells you the state of puppetctl locks (who made them, what type, when they expire).
* **motd-status**
Tells you the state of any puppetctl locks, or stays quiet when there are no locks.

### Modification Commands
Modification commands require root.
* **enable**
Removes your disable lock (if you have one).
* **disable**
Adds a disable lock for you, preventing future puppet runs.
* **operate**
Removes your nooperate lock (if you have one)
* **nooperate**
Adds a nooperate lock for you, placing future puppet runs into noop mode.
* **run**
Runs puppet (if not disabled).  If there is a nooperate lock, `puppet agent` will run with `--noop`.

### Emergency Commands
Emergency commands require root and `--force`
* **break-all-locks**
Forcibly removes all locks on a host.  You should not use this, but instead should talk to whoever else placed a lock, and verify it is safe to remove.  But for completeness, here it is.
* **panic-stop**
Kills an actively-running `puppet agent`.  This is likely not useful, but terminating a puppet run was not uncommon in the original `puppetctl` world, so this is here.
