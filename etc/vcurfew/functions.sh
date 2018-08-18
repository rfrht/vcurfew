# Loads HTML header and body
cat /etc/vcurfew/html/header.html
cat /etc/vcurfew/html/body.html


# Redirect STDERR to STDOUT, so errors are printed in the resulting page.
exec 2>&1


if [ $DEBUG == "true" ] ; then
   set -e -x
fi

# Disable internationalizations (and potential syntax issues)
for i in LC_PAPER LC_MONETARY LC_NUMERIC LC_MEASUREMENT LC_TIME LANG LANGUAGE TZ ; do
   unset $i
done


# Configure logging functions
log.debug() {
if [ $DEBUG == "true" ] ; then
   echo DEBUG: $@
fi
}
log.error() {
echo ERROR: $@
}
print.html() {
   echo "<H2><P>$@</P></H2>"
}


# Test if sqlite has the correct permissions
if [ $TESTWRITE == "yes" ] ; then
   if sqlite $SQDB "CREATE TABLE test(test,integer)" ; then
      sqlite $SQDB "DROP TABLE test"
   else
      log.error "sqlite does not have write permission in file $SQDB and its directory."
      log.error "Check permissions and try again."
      exit 1
   fi
fi


# Function net_unlock - Unlocks internet, write the token and 
# schedules the next lockout. Input parameter: $@ ; when to
# lockdown again.
net_unlock() {
UUID=$(uuid)
for i in $(sqlite $SQDB "SELECT mac FROM systems WHERE user='$USER'" | sed 's/..\B/&:/g') ; do
# TODO: ENSURE THAT BLOCKING RULE EXISTS AND IS PRESENT.
# if ! iptables -nvL | grep "MAC $i" ; then
#    iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j DROP
# fi
   # run right now
   sudo /sbin/iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j ACCEPT
   sudo /sbin/iptables -t nat -D PREROUTING -i $INTERFACE ! -d $CAPTIVE_PORTAL -m mac --mac-source $i -p tcp --dport 80 -j DNAT --to $CAPTIVE_PORTAL:8081
   # Schedule for at job
   echo "sudo /sbin/iptables -D FORWARD -i $INTERFACE -m mac --mac-source $i -j ACCEPT" >> /dev/shm/$UUID
   echo "sudo /sbin/iptables -t nat -I PREROUTING -i $INTERFACE ! -d $CAPTIVE_PORTAL -m mac --mac-source $i -p tcp --dport 80 -j DNAT --to $CAPTIVE_PORTAL:8081" >> /dev/shm/$UUID
done

if [ -z $AUTHORIZED_MINUTES ]; then
   AUTHORIZED_MINUTES = 0
fi

if [ ! -e /dev/shm/$UUID ] ; then
   log.error "O usu&aacute;rio $USER n&atilde;o existe - Imposs&iacute;vel liberar acesso."
   exit 1
else
   sqlite $SQDB "INSERT INTO tokens VALUES ('$USER', datetime('now', 'localtime'), $AUTHORIZED_MINUTES)"
   echo rm /dev/shm/$UUID >> /dev/shm/$UUID
   log.debug "Executando net_unlock() com $@"
   cat /dev/shm/$UUID | TZ=$TIMEZONE at $@
fi
}
