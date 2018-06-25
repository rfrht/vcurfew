#!/bin/bash -x

echo "Content-type: text/plain"
echo ""


# Load initial setup
source /etc/vcurfew/config.txt


# Translate the IP address to a MAC address. Sanitizes the values.
MAC=$(arp -an | awk "match (\$0,/$REMOTE_ADDR/) {print \$4}" | tr -dc '[:xdigit:]' | tr '[:lower:]' '[:upper:]' | cut -c -12)
echo "MAC equals $MAC"


# Check if is there a user assigned to that MAC address. Loads the USER variable.
USER=$(sqlite $SQDB "SELECT user FROM systems WHERE mac='$MAC'")
if [ -z $USER ] ; then
   echo "MAC $MAC not found"
   exit 1
else
   echo "User $USER has MAC $MAC."
fi


# Looks up the user configuration and characterics
CONFIG=($(sqlite -separator " " $SQDB "SELECT * FROM users WHERE user='$USER'" ))
if [ -z $CONFIG ] ; then
   echo "This should not happen - user $USER exists in 'systems' and does not exist in 'users'."
   exit 1
fi
echo "Config array result: ${CONFIG[*]}"
echo "Array syntax: USER - DUR/WKDY - DUR/WKND - HR/INI - HR/EOD - TOKENS/WKDY - TOKENS/WKND"


# Transforms the array into human-readable variables.
DUR_WKDY=${CONFIG[1]}
DUR_WKND=${CONFIG[2]}
HOUR_INI=${CONFIG[3]}
HOUR_EOD=${CONFIG[4]}
TOKEN_WKDY=${CONFIG[5]}
TOKEN_WKND=${CONFIG[6]}
HOUR_NOW=$(TZ="$TIMEZONE" date +"%H")
TODAY=$(TZ="$TIMEZONE" date +"%a")
WKND_DAYS="Sat Sun"


# Function - Unlocks internet, write the token and schedules the next
# curfew implementation.
net_unlock() {
echo "INSERT INTO tokens VALUES ('$USER', datetime('now', 'localtime'), 1);" | sqlite /etc/vcurfew/vcurfew
for i in $(sqlite $SQDB "SELECT mac FROM systems WHERE user='$USER'" | sed 's/..\B/&:/g') ; do
   echo "echo sudo /sbin/iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j ACCEPT"
   echo "echo sudo /sbin/iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j DROP" >> /dev/shm/$UUID
done
echo rm /dev/shm/$UUID >> /dev/shm/$UUID
}


# Is the access request during authorized hours?
if [[ $HOUR_NOW -lt $HOUR_INI || $HOUR_NOW -ge $HOUR_EOD ]] ; then
   echo "You are outside the authorized hours. Request access between $HOUR_INI and $HOUR_EOD"
   exit 0
else
   echo "Valid time; moving on"
fi


# Checks for weekdays or weekends
if [[ $WKND_DAYS =~ $TODAY ]] ; then
   echo "DOW: Weekend"
   AUTHORIZED_HOURS=$DUR_WKND
   TOKENS_AUTHORIZED=$TOKEN_WKND
else
   echo "DOW: Weekday"
   AUTHORIZED_HOURS=$DUR_WKDY
   TOKENS_AUTHORIZED=$TOKEN_WKDY
fi


# Checks if is there any already active token
TOKEN_EPOCH=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT MAX(strftime ('%s', token_epoch, )) FROM tokens WHERE token_epoch >= DATE('now', 'localtime') AND user = '$USER'" )
if [ -z $TOKEN_EPOCH ] ; then
   echo "No active tokens, moving on"
   echo "Token epoch = $TOKEN_EPOCH"
   let GOOD_THRU="$TOKEN_EPOCH+3600*$AUTHORIZED_HOURS"
   EPOCH_NOW=$(date +"%s")
   let SECONDS_VALID="$GOOD_THRU-$EPOCH_NOW"
   echo "So this is it: Current epoch $EPOCH_NOW, Token issued at $TOKEN_EPOCH and valid until $GOOD_THRU. Valid for more $SECONDS_VALID seconds."
else
   echo "Token epoch value: $TOKEN_EPOCH"
   let "GOOD_THRU=$TOKEN_EPOCH+3600*$AUTHORIZED_HOURS"
   EPOCH_NOW=$(date +"%s")
   let SECONDS_VALID="$GOOD_THRU-$EPOCH_NOW"
   echo "So this is it: Current epoch $EPOCH_NOW, Token issued at $TOKEN_EPOCH and valid until $GOOD_THRU. Valid for more $SECONDS_VALID seconds."
   if [[ $EPOCH_NOW -gt $TOKEN_EPOCH && $EPOCH_NOW -lt $GOOD_THRU ]] ; then
      echo "There's a valid and active token. Exiting, no action taken."
      exit 0
   fi
fi


# Check for token balance
TOKENS_CONSUMED_TODAY=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT COUNT(*) FROM tokens WHERE DATE(token_epoch, 'localtime') >= DATE('now', 'localtime') AND user = '$USER'")
echo "Tokens Consumed Today: $TOKENS_CONSUMED_TODAY"
echo "Total allowed Tokens for today: $TOKENS_AUTHORIZED"
if [ $TOKENS_CONSUMED_TODAY -ge $TOKENS_AUTHORIZED ] ; then
   echo "You are out of token quota. Allowed tokens: $TOKENS_AUTHORIZED, consumed tokens: $TOKENS_CONSUMED_TODAY"
   exit 1
fi


# Issue the access token
UUID=$(uuid)
let "HOURS_UNTIL_EOD=$HOUR_EOD-$HOUR_NOW"
if [ $HOURS_UNTIL_EOD -le $AUTHORIZED_HOURS ] ; then
   echo "Access allowed until $HOUR_EOD hours".
   net_unlock
   cat /dev/shm/$UUID | TZ=$TIMEZONE at $HOUR_EOD:00
else
   echo "Authorizing $AUTHORIZED_HOURS hours, good thru $(TZ=$TIMEZONE date -d "+$AUTHORIZED_HOURS hours" +"%Hh%M")."
   net_unlock
   cat /dev/shm/$UUID | at NOW + $AUTHORIZED_HOURS hours
fi

