#!/bin/bash

CON_SSHC="sshpass -p CONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP"

# COLOR ENCODING
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'


function cprint {
  char=$1
  size=$2

  for ((i = 0 ; i < $(( size + 4 )) ; i++ )); do
    echo -n "$char"
  done
  echo ""
}

function headerR {
  msg=$1
  siz=${#msg}

  echo -en "${RED}"
  cprint "*" $siz
  echo "* $msg *"
  cprint "*" $siz
  echo -en "${NC}"
}

function headerY {
  msg=$1
  siz=${#msg}

  echo -en "${YELLOW}"
  cprint "*" $siz
  echo "* $msg *"
  cprint "*" $siz
  echo -en "${NC}"
}

function put_choices {
  echo -e "$1${RED}"
  for ((i = 2 ; i <= $# ; i++ )); do
    echo "  ${!i}"
  done
  echo -en "${NC}  "
}

function read_resp {
  read resp
  echo $resp|tr '[:upper:]' '[:lower:]';
}

function CONTROLLER_CMD {
  cmd=$1;
  $CON_SSHC "$cmd";
  echo "$?";
}

function CONTROLLER_CMDv1 {
  cmd=$1;
  $CON_SSHC "$cmd" > /dev/null 2>&1;
}

function CONTROLLER_CMDv2 {
  cmd=$1;
  res=$($CON_SSHC "$cmd" 2>/dev/null);
  echo "$res";
}

function REPORT {
  res=$1;
  msg=$2;

  if [ $res == 0 ]; then
    echo "$msg OK";
  else
    echo "$msg NOK";
    exit 1;
  fi
}

function seperator {
  echo "";
  echo "----------------------------------";
  echo "";
}
