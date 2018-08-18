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


# Load initial setup
source /etc/vcurfew/config.txt
source /etc/vcurfew/functions.sh


# Translate the IP address to a MAC address. Sanitizes the values.
MAC=$(arp -an $REMOTE_ADDR | awk '{gsub(/:/, "", $4); print toupper($4)}')
log.debug "MAC equals $MAC"


# Check if is there a user assigned to that MAC address. Loads the USER variable.
USER=$(sqlite $SQDB "SELECT user FROM systems WHERE mac='$MAC'")
if [ -z $USER ] ; then
   log.debug "MAC $MAC not found - Not managed."
   print.html "Ol&aacute;! Voc&ecirc; n&atilde;o &eacute; gerenciado."
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
   EXPIRES_AT=$(TZ=$TIMEZONE date +"%R" --date="@$GOOD_THRU")
   log.debug "There's a valid and active token. Exiting, no action taken."
   print.html "Ainda h&aacute; uma sess&atilde;o ativa, v&aacute;lida at&eacute; &agrave;s $EXPIRES_AT ! Viva o Cachuco!"
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
      net_unlock $HOUR_EOD:00
   else
      log.debug "Authorizing $AUTHORIZED_HOURS hours, good thru $(TZ=$TIMEZONE date -d "+$AUTHORIZED_HOURS hours" +"%Hh%M")."
      print.html "Iniciando sess&atilde;o de $AUTHORIZED_HOURS horas. V&aacute;lida at&eacute; &agrave;s $(TZ=$TIMEZONE date -d "+$AUTHORIZED_HOURS hours" +"%Hh%M")."
      print.html "O p&atilde;rp&atilde;r e seus computadores te desejam um bom uso!"
      let AUTHORIZED_MINUTES=$AUTHORIZED_HOURS*60
      net_unlock NOW + $AUTHORIZED_MINUTES minutes
   fi
fi
