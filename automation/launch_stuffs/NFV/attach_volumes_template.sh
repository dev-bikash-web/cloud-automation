#!/bin/bash

while [ -s CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg ]; do

  while IFS="\ " read -r vol_name vnf_id; do
    if [[ "${vnf_id}" != "0" && "${vnf_id}" != "1" ]]; then
      echo "[$(date)]${vol_name} ${vnf_id}" >> CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/attach_volumes.log
      source CFW_NFV_BASE_SUB_PATH/SOURCE_FILE
      openstack server add volume ${vnf_id} ${vol_name}
      echo "Attach initiated for "${vol_name}" at "$(date)"" >> CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/attach_volumes.log
      sleep 3
      status=$(openstack volume show ${vol_name} | grep in-use)
      attached_host=$(openstack volume show ${vol_name} | grep ${vnf_id})
      echo "Checking status... "$(date)"" >> CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/attach_volumes.log
      if  [ "$status" == "" -o "$attached_host" == "" ]; then
        continue
      else
        sed -i "s/${vol_name}\ ${vnf_id}/${vol_name}\ 1/g" CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg
      fi
      echo "Checked status... "$(date)"" >> CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/attach_volumes.log
    fi
  done < "CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg"

  sleep 30
done
