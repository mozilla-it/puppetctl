# MAINTAINERS notes
`puppetctl` has a long history with us, so this captures some of the design decisions taken as we go to this release.

## Time
There were 3 ways to specify time originally.
* By habit, most people used the `at(1)` syntax of `'now + 2 hours'` (when they specified time at all, rather than accepting the default 1 hour).
* There was also the ability to do a more brief `'+2h'`.  This was more rare, but since it was possible, we kept that.
* There were also various flavors of YYYYMMDDhhmmss that could be accepted.  Polling revealed nobody would miss that, so we ditched it during the rewrite from bash to python.
* The original puppetctl used `at(1)` as its time manager.  With the rewrite to python we have removed the need for `at(1)` and instead emulate the time parser, some might say naively.  The parser is isolated into a `_uniform_time_parser` method that we can expand as needed.

## Locks
The original puppetctl was written with the host in mind: the host is either enabled or disabled.  We added an ability to be enabled-but-noop'ed, so we could make changes and guarantee that they wouldn't be executed.  But it was still "this is how the the state of the host."
In the rewrite, we shifted this slightly and incorporated the [Lockout-Tagout](https://en.wikipedia.org/wiki/Lockout%E2%80%93tagout#Group_lockout) mindset.  Each user may add and remove locks to a host indicating that they want the host disabled, or enabled-but-noop'ed.  As long as anyone wants it disabled, it's disabled.  As long as anyone wants it noop'ed, it's noop'ed.  You can add a noop on top of someone else's disable: the disable will prevail, but if the disable is removed your noop is still in place.
Just like in real life, you can break all locks and put a host into service, but it's a deliberate act and puppetctl discourages you along the way.
And if all that sounds confusing, in a world where just one person is working on a host, nothing much has changed in the user experience.

## Stopping Puppet
puppetctl used to prevent you from adding a lock when puppet was running.  Killing off puppet happened when using 'puppetctl disable -f'.  In the rewrite, a lock can be added while puppet is running, it will just tell you that puppet is running, and if you meant to kill it to use panic-stop.  It's unclear that people really ever wanted/needed to kill an active puppet run, but we have moved that ability out of 'disable' and into 'panic-stop', which kills a run.  It's probably not needed anymore, though.
