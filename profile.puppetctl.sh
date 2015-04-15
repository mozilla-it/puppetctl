if [[ -f /var/lib/puppetctl.status ]]; then
   if [[ "$(ps -ocommand= -p $PPID)" =~ "sshd" ]]; then
      if echo "$-" | grep -q i; then
         echo -e "\033[1;31m$(cat /var/lib/puppetctl.status)\033[0m"
      fi
   fi
fi
