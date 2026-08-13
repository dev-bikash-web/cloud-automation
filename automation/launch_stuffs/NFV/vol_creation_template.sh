#!/bin/bash

source CFW_NFV_BASE_SUB_PATH/SOURCE_FILE

########################################
ip_address=CFW_NODE1_PHYSICAL_IPV4
vol_name="CFW_NAME_NODE1_`echo $ip_address | cut -d . -f 4`"
check_volume=$(openstack volume list | grep $vol_name)
if [ -z "$check_volume" ];
then
  echo "Creating CFW Node 1 volume..."
  openstack volume create --size CFW_VOLUME_SIZE --availability-zone CFW_VOLUME_ZONE $vol_name
  echo "Writing $vol_name in CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg"
  echo "$vol_name 0" > CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg
else
  echo "Writing $vol_name in CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg"
  echo "$vol_name 0" > CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg
  echo "Volume of CFW Node1 named $vol_name already created. So, skipping creation ..."
fi
########################################

awk '!seen[$0]++' volume_check.cfg > temp.cfg
cat temp.cfg > volume_check.cfg
rm temp.cfg

#service load_volumeservice restart
