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


# Look up config for OTP SHA1. If not defined, halt and catch fire.
if [ -z $OTPSHA1 ] ; then
   log.error "Please configure a SHA1 for the one-time passwords. Ensure to install oathtool too."
   exit 1
fi

# Read the form POST and sanitize it
read -N $CONTENT_LENGTH QUERY_STRING_POST
QS=($(echo $QUERY_STRING_POST | tr '&' ' '))
USER=$(echo ${QS[0]} | awk -F = '{print $2}' | tr -dc '[:alnum:]' | cut -b -8)
AUTHORIZED_MINUTES=$(echo ${QS[1]} | awk -F = '{print $2}' | tr -dc '[:digit:]' | cut -b -3)
CODE=$(echo ${QS[2]} | awk -F = '{print $2}' | tr -dc '[:digit:]' | cut -b -6)


# Execution decision chain
if [ -z $AUTHORIZED_MINUTES ] || [-z $AUTHORIZED_MINUTES] || [-z $USER ] ; then
   log.error "One or more required parameters are missing. Please check the form."
   exit 1
elif [ $CODE != $(oathtool --totp $OTPSHA1) ] ; then
   log.error "Invalid one-time password"
   exit 1
else
   net_unlock NOW + $AUTHORIZED_MINUTES minutes
fi
