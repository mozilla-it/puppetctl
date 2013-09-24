# The following case statement was used based on information obtained from:
# http://www.tldp.org/LDP/abs/html/intandnonint.html
if [[ -f /var/run/puppetctl.status ]]; then
   if [[ "$(ps -ocommand= -p $PPID)" =~ "sshd" ]]; then
      if [[ $( case $- in *i*) echo 1 ;; *) echo 0 ;; esac ) == '1' ]]; then
         echo -e "\033[1;31m$(cat /var/run/puppetctl.status)\033[0m"
      fi
   fi
fi
