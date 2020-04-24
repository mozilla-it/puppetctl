# shellcheck disable=SC2148
# This is a profile file, no-shebang is appropriate
#
# zsh code contributed by https://github.com/neoice, see
# https://github.com/mozilla-it/puppetctl/issues/10#issuecomment-93522647
# for more information
#

readonly STATUSFILE=/var/lib/puppetctl.status
if [[ -f $STATUSFILE ]]; then
   case $(basename $SHELL) in
      bash)
         if [[ "$(ps -ocommand= -p $PPID)" =~ "sshd" ]]; then
            if echo "$-" | grep -q i; then
               echo -e "\\033[1;31m$(cat $STATUSFILE)\\033[0m"
            fi
         fi
         ;;
      zsh)
         if [[ $- != *i* ]] ; then
            # shell is not interactive, leave now!
            return
         fi
         echo -e "\033[1;31m$(cat $STATUSFILE)\033[0m"
         ;;
      *)
         echo "WARNING: Shell unsupported. Puppet may be disabled."
         ;;
   esac
fi
