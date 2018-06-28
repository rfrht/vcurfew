#!/bin/bash

set -e

echo "Content-type: text/html"
echo ""


# Sanitize form entries
if [ ! -z ${QUERY_STRING[0]} ] ; then
   FORM_ACTION=$(echo ${QUERY_STRING[0]} | tr -dc '[:alpha:]' )
else
   FORM_ACTION=0
fi


# Prepare debug messages parsing
log.debug () {
if [ $DEBUG == "true" ] ; then
   set -e -x
   echo DEBUG: $@
fi
}

log.error () {
echo ERROR: $@
}

print.html () {
   echo "<H2><P>$@</P></H2>"
}

# Load initial setup
source /etc/vcurfew/config.txt


# Redirect STDERR to STDOUT, so errors are printed in the resulting page.
exec 2>&1


# Loads HTML header and body
cat /etc/vcurfew/html/header.html
cat /etc/vcurfew/html/body.html


# Disable internationalizations (and potential syntax issues)
for i in LC_PAPER LC_MONETARY LC_NUMERIC LC_MEASUREMENT LC_TIME LANG LANGUAGE TZ ; do 
   unset $i
done


if [ $TESTWRITE == "yes" ] ; then
   # Test if sqlite has the correct permissions
   if sqlite $SQDB "CREATE TABLE test(test,integer)" ; then
      sqlite $SQDB "DROP TABLE test"
   else
      log.error "sqlite does not have write permission in file $SQDB and its directory."
      log.error "Check permissions and try again."
      exit 1
   fi
fi


# Translate the IP address to a MAC address. Sanitizes the values.
MAC=$(arp -an $REMOTE_ADDR | awk '{gsub(/:/, "", $4); print toupper($4)}')
log.debug "MAC equals $MAC"


# Check if is there a user assigned to that MAC address. Loads the USER variable.
USER=$(sqlite $SQDB "SELECT user FROM systems WHERE mac='$MAC'")
if [ -z $USER ] ; then
   log.debug "MAC $MAC not found - Not managed."
   exit 1
else
   log.debug "User $USER has MAC $MAC."
fi


# Looks up the user configuration and characterics
CONFIG=($(sqlite -separator " " $SQDB "SELECT * FROM users WHERE user='$USER'" ))
if [ -z $CONFIG ] ; then
   log.error "This should not happen - user $USER exists in 'systems' and does not exist in 'users'."
   exit 1
fi
log.debug "Config array result: ${CONFIG[*]}"
log.debug "Array syntax: USER - DUR/WKDY - DUR/WKND - HR/INI - HR/EOD - TOKENS/WKDY - TOKENS/WKND"


# Transforms the array into human-readable variables.
DUR_WKDY=${CONFIG[1]}
DUR_WKND=${CONFIG[2]}
HOUR_INI=${CONFIG[3]}
HOUR_EOD=${CONFIG[4]}
TOKEN_WKDY=${CONFIG[5]}
TOKEN_WKND=${CONFIG[6]}
HOUR_NOW=$(TZ="$TIMEZONE" date +"%-H")
TODAY=$(TZ="$TIMEZONE" date +"%a")
WKND_DAYS="Sat Sun"


# Function - Unlocks internet, write the token and schedules the next
# curfew implementation. Currently this is only a stub (echoing).
net_unlock() {
sqlite $SQDB "INSERT INTO tokens VALUES ('$USER', datetime('now', 'localtime'), 1)"
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
echo rm /dev/shm/$UUID >> /dev/shm/$UUID
}


# Is the access request during authorized hours?
if [[ $HOUR_NOW -lt $HOUR_INI || $HOUR_NOW -ge $HOUR_EOD ]] ; then
   log.debug "You are outside the authorized hours. Request access between $HOUR_INI and $HOUR_EOD"
   exit 0
else
   log.debug "Valid time; moving on"
fi


# Checks for weekdays or weekends
if [[ $WKND_DAYS =~ $TODAY ]] ; then
   log.debug "DOW: Weekend"
   AUTHORIZED_HOURS=$DUR_WKND
   TOKENS_AUTHORIZED=$TOKEN_WKND
else
   log.debug "DOW: Weekday"
   AUTHORIZED_HOURS=$DUR_WKDY
   TOKENS_AUTHORIZED=$TOKEN_WKDY
fi


# Checks if is there any already active token
TOKEN_EPOCH=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT MAX(strftime ('%s', token_epoch, )) FROM tokens WHERE token_epoch >= DATE('now', 'localtime') AND user = '$USER'" )
GOOD_THRU=$(($TOKEN_EPOCH+3600*$AUTHORIZED_HOURS))
EPOCH_NOW=$(date +"%s")
SECONDS_VALID=$(($GOOD_THRU-$EPOCH_NOW))
log.debug "Current epoch $EPOCH_NOW, Token issued at $TOKEN_EPOCH and valid until $GOOD_THRU. Valid for more $SECONDS_VALID seconds."
if [[ $EPOCH_NOW -gt $TOKEN_EPOCH && $EPOCH_NOW -lt $GOOD_THRU ]] ; then
   log.debug "There's a valid and active token. Exiting, no action taken."
   print.html "Ainda h&aacute; uma sess&atilde; ativa! Viva o Cachuco!"
   exit 0
fi


# Check for token balance
TOKENS_CONSUMED_TODAY=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT COUNT(*) FROM tokens WHERE DATE(token_epoch, 'localtime') >= DATE('now', 'localtime') AND user = '$USER'")
TOKEN_BALANCE=$(($TOKENS_AUTHORIZED-$TOKENS_CONSUMED_TODAY))
log.debug "Tokens Consumed Today: $TOKENS_CONSUMED_TODAY"
log.debug "Total allowed Tokens for today: $TOKENS_AUTHORIZED"
if [ $TOKENS_CONSUMED_TODAY -ge $TOKENS_AUTHORIZED ] ; then
   log.debug "You are out of token quota. Allowed tokens: $TOKENS_AUTHORIZED, consumed tokens: $TOKENS_CONSUMED_TODAY"
   print.html "<center>Voc&ecirc; consumiu as $TOKENS_CONSUMED_TODAY sess&otilde;es de hoje :-("
   print.html "Mas &acirc;nimo: Amanh&atilde; tem mais :-)</center>"
   exit 1
fi


# Present a (rudimentary) form prompting for a token.
if [ $FORM_ACTION != "actionstart" ] ; then
   cat << EOF
<H2><P>Voc&ecirc; tem um saldo de $TOKEN_BALANCE sess&otilde;es (de $TOKENS_AUTHORIZED no total)
<BR>de $AUTHORIZED_HOURS horas cada.
<P>Voc&ecirc; quer iniciar uma sess&atilde;o?</H2>
<FORM ACTION='/cgi-bin/vcurfew1.cgi' METHOD='GET'>
<INPUT TYPE='hidden' NAME='action' VALUE='start'>
<INPUT TYPE='submit' VALUE='Iniciar Sess&atilde;o'>
</FORM>
EOF
   exit 0
else
   # Button pressed - Issue the access token
   UUID=$(uuid)
   HOURS_UNTIL_EOD=$(($HOUR_EOD-$HOUR_NOW))
   if [ $HOURS_UNTIL_EOD -le $AUTHORIZED_HOURS ] ; then
      log.debug "Access allowed until $HOUR_EOD hours".
      print.html "Autorizando acesso at&eacute; &agrave;s $HOUR_EOD horas."
      net_unlock
      cat /dev/shm/$UUID | TZ=$TIMEZONE at $HOUR_EOD:00
   else
      log.debug "Authorizing $AUTHORIZED_HOURS hours, good thru $(TZ=$TIMEZONE date -d "+$AUTHORIZED_HOURS hours" +"%Hh%M")."
      print.html "Iniciando sess&atilde;o de $AUTHORIZED_HOURS horas. V&aacute;lida at&eacute; &agrave;s $(TZ=$TIMEZONE date -d "+$AUTHORIZED_HOURS hours" +"%Hh%M")."
      print.html "O p&atilde;rp&atilde;r e seus computadores te desejam um bom uso!"
      net_unlock
      cat /dev/shm/$UUID | at NOW + $AUTHORIZED_HOURS hours
   fi
fi
