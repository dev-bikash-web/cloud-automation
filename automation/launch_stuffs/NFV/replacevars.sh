#!/bin/bash

source helper.sh
headerY "$0"
echo ""

home_dir=$(echo $HOME)
source_file=`awk '/SOURCE_FILE/ { print $2 }' wigw_config.cfg`
base_dir=`awk '/CFW_NFV_BASE_SUB_PATH/ { print $2 }' wigw_config.cfg`
nfvname=`awk '/CFW_NFV_CONTROLLER_DIR/ { print $2 }' wigw_config.cfg`
mode=`awk '/CFW_HA_MODE/ { print $2 }' wigw_config.cfg`
nodename=`awk '/CFW_NFV_VM_NODE_TYPE/ { print $2 }' wigw_config.cfg`


if [ "$home_dir" != "$base_dir" ]; then
  if [ -f $home_dir/$source_file ]; then
    cp $home_dir/$source_file $base_dir
  fi
fi

while read -r key value
do
  echo "s;$key;$value;g" >> sedtmpfile
  if [ "$key" == "NODE_DETAILS_END" ]; then
    break;	 
  fi
done < wigw_config.cfg

sed -i "/s\;\#/d" sedtmpfile
sed -i "/\;\;g/d" sedtmpfile


if [ "$1" == "275" ]; then
  echo "Running inside VM (275)"
  sed -i -f sedtmpfile helper.sh
  sed -i -f sedtmpfile configure_cfw.sh
  echo "Exiting from $0"
  exit # NO NEED TO PROCEED FURTHER
fi

echo "Checking configuration file"
if [ "$nodename" == "EPDGDP" ]; then
  echo "Node is EPDGDP, running config validation for EPDGDP"
  python3 cfg_validation.py epdgdp "3.1.0"
else
  echo "Node is $nodename, running config validation for TWAGDP"
  python3 cfg_validation.py twagdp "3.1.0"
fi
ret=$?
if [ "$ret" != 0 ]; then
 echo "Configuration file is not OK, Please check the configuration and again run this command."
 exit 1;
fi
echo "Configuration file is OK"

if [ "$#" -ne 1 ]; then
  put_choices "CAUTION: Please ensure ${RED}wigw_config.cfg${NC} is modified to run CFW nodes!"\
    "Hit 'Ctrl+C' to EXIT, if not done"\
    "Hit ENTER to continue."

    read
    put_choices "Please enter your choice"\
      "1: Prepare VNFDs to both Onboard and Deploy [When VNFDs is not yet onboarded]"\
      "2: Only Deploy [When VNFDs are already onboarded]"

    read choice
fi

if [ "$choice" == "1" ]; then

  if [ ! -d "generated_vnf_ns/" ]; then
    mkdir generated_vnf_ns
  else
    rm -f generated_vnf_ns/*
  fi

  
  sed -f sedtmpfile cfw_node1_template.yaml      > generated_vnf_ns/${nfvname}_node1.yaml
  sed -f sedtmpfile ns_param_template.yaml       > generated_vnf_ns/ns_param.yaml
  sed -f sedtmpfile vol_creation_template.sh     > generated_vnf_ns/volume_creator.sh
  sed -f sedtmpfile attach_volumes_template.sh   > generated_vnf_ns/attach_volumes.sh

  if [ ! -f "volume_check.cfg" ]; then
    touch volume_check.cfg
  fi

  headerY "The VNFDs & NS files are generated in 'generated_vnf_ns/' of current working directory"

  headerR "VOLUME CREATION TIME"
  chmod 777 generated_vnf_ns/volume_creator.sh
  ./generated_vnf_ns/volume_creator.sh

elif [ "$choice" == "2" ]; then

  sed -f sedtmpfile ns_param_template.yaml    > generated_vnf_ns/ns_param.yaml
  sed -f sedtmpfile vol_creation_template.sh  > generated_vnf_ns/volume_creator.sh

  headerR "VOLUME CREATION TIME"
  chmod 777 generated_vnf_ns/volume_creator.sh
  ./generated_vnf_ns/volume_creator.sh
fi

chmod 777 generated_vnf_ns/attach_volumes.sh
cmd_vol=`ps -ef|grep ${base_dir}/${nfvname}/NFV/generated_vnf_ns/attach_volumes.sh | wc -l`
if [ "$cmd_vol" == 1 ] ; then
  ${base_dir}/${nfvname}/NFV/generated_vnf_ns/attach_volumes.sh &
fi
rm -f sedtmpfile
