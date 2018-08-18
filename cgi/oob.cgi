#!/bin/bash
echo "Content-type: text/html"
echo ""

# Are we actually processing something here?
if [ "$REQUEST_METHOD" != "POST" ] ; then
   cat /etc/vcurfew/html/addtoken.html
   exit 0
fi

# Load initial setup
source /etc/vcurfew/config.txt
source /etc/vcurfew/functions.sh

read -N $CONTENT_LENGTH QUERY_STRING_POST
QS=($(echo $QUERY_STRING_POST | tr '&' ' '))

USER=$(echo ${QS[0]} | awk -F = '{print $2}' | tr -dc '[:alnum:]' | cut -b -8)
AUTHORIZED_MINUTES=$(echo ${QS[1]} | awk -F = '{print $2}' | tr -dc '[:digit:]' | cut -b -3)
CODE=$(echo ${QS[2]} | awk -F = '{print $2}' | tr -dc '[:digit:]' | cut -b -6)

if [ -z $AUTHORIZED_MINUTES ] ; then
   log.error "No minutes specified."
   exit 1
elif [ $CODE != $(oathtool --totp $OTPSHA1) ] ; then
   log.error "C&oacute;digo n&atilde;o vale"
   exit 1
else
   net_unlock NOW + $AUTHORIZED_MINUTES minutes
fi
