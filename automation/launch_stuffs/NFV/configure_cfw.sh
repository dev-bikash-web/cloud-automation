#!/bin/bash

###############################################################################
# Setup logging API for the module, log to a file along with echo on terminal.#
#                                                                             #
# Read the version from the configuration file for logging.                   #
###############################################################################
LOGPATH="/var/log/"
LOGFILE="wigw_nfv_configuration.log"
AUTOCONFIG_DONE="/opt/cfw/auto_cfg_done"

function GET_CFG_VERSION {
  cfg_file=""
  for file in /root/wigw_config.cfg wigw_config.cfg; do
    if [ -f "$file" ]; then
      cfg_file="$file"
      break
    fi
  done

  if [ -z "$cfg_file" ]; then
    echo "unknown"
    return
  fi

  awk '
    /^[[:space:]]*\[CFG_VERSION\][[:space:]]*$/ { in_section=1; next }
    /^[[:space:]]*\[/ { in_section=0 }
    in_section && /^[[:space:]]*version[[:space:]]*=/ {
      sub(/^[^=]*=[[:space:]]*/, "", $0)
      sub(/[[:space:]]*(#.*)?$/, "", $0)
      print
      exit
    }
  ' "$cfg_file"
}

VERSION=$(GET_CFG_VERSION)
VERSION=${VERSION:-unknown}

function LOG {
  message=$1;
  datetime=`date +"%b %d %T"`
  echo -e "$message";
  echo -e "$datetime $message" >> $LOGPATH/$LOGFILE;
}

function BLOCK {
  LOG "========================================================================"
}

SSH_C="ssh -o StrictHostKeyChecking=no"
CONTROLLER_CMD="sshpass -pCONTROLLER_PASSWORD $SSH_C CONTROLLER_USER@CONTROLLER_IP"
COMPUTE_CMD="sshpass -pCOMPUTE_PASSWORD $SSH_C COMPUTE_USER@COMPUTE_IP"
cfw

BLOCK
LOG "using CFW NFV version - $VERSION"


LOG "current routes -"
LOG "`sudo ip route show`"


###############################################################################
# Remove the known host key first and then add the host key by running a dummy#
# ssh command.                                                                #
###############################################################################
LOG "removing controller ip address: CONTROLLER_IP from ssh known_hosts"
ssh-keygen -f "/root/.ssh/known_hosts" -R "CONTROLLER_IP" > /dev/null 2>&1
$CONTROLLER_CMD "uptime" > /dev/null 2>&1


ip_address=CFW_NODE1_PHYSICAL_IPV4
LOG "node ip address: $ip_address"


################################################################################
# Mount check. Check the volume is already mounted in /opt/cfw. This will save #
# us some time in case of reboot.                                              #
################################################################################
mount_check=`mount | grep /opt/cfw`

if [ "$mount_check" == "" ]; then

  BLOCK
  LOG "volume not mounted"

  ##############################################################################
  # Host Entry for openstacklocal in /etc/hosts                                #
  ##############################################################################
  hosts=`hostname`
  entry="127.0.1.1       $hosts.openstacklocal     $hosts"
  found=$(grep -iq "$entry" /etc/hosts)
  if [ "$found" != "0" ]; then
    LOG "making hosts entry for 127.0.1.1"
    echo "$entry" >> /etc/hosts
  else
    LOG "host entry for 127.0.1.1 already present."
  fi


  LOG "replace resolv.conf and restart resolvd service"
  sudo unlink /etc/resolv.conf
  sudo ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
  sudo systemctl restart systemd-resolved
  sudo systemctl status systemd-resolved > /dev/null 2>&1


  ##############################################################################
  # TODO: PENDING NTP CONFIGURATION Check                                      #
  # Get the VNF id and volume name                                             #
  #   * Replace VNF_ID in volume_check.cfg file in controller                  #
  #   * Run attach_volumes script in controller                                #
  ##############################################################################
  BLOCK
  $CONTROLLER_CMD ". CFW_NFV_BASE_SUB_PATH/SOURCE_FILE; openstack server list | grep -w \"\b$ip_address\b\" " > server_props
  VNF_ID=$(cut -d " " -f 2 server_props)
  vol_name="CFW_NAME_NODE1_`echo $ip_address | cut -d . -f 4`"

  LOG "VNF_ID = $VNF_ID"
  LOG "VOLUME = $vol_name"

  $CONTROLLER_CMD ". CFW_NFV_BASE_SUB_PATH/SOURCE_FILE; openstack volume show $vol_name | grep in-use" > volume_state

  LOG "preparing volume_check.cfg.."
  $CONTROLLER_CMD "sed -i -e '/$vol_name/c\\$vol_name\ $VNF_ID' CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg"

  LOG "check attach_volume script"
  volpid=$($CONTROLLER_CMD "ps -ef | grep CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/generated_vnf_ns/attach_volumes.sh | grep -v grep | awk '{print \$2}'")
  volpid=${volpid// /}

  if [ ! -z "$volpid" ]; then
    LOG "attach_volume.sh script already running!"
  else
    LOG "running attach_volume.sh script at controller"
    $CONTROLLER_CMD "CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/generated_vnf_ns/attach_volumes.sh </dev/null >/dev/null 2>&1 &"
  fi

  check=0
  while [ "$check" == "0" ];
  do
    $CONTROLLER_CMD "cat CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg" > vol_check.cfg

    LOG "  checking the entry for volume"
    while IFS="\ " read volume value
    do
      if [[ "$vol_name" == "$volume" && "$value" == "1" ]]; then
        check=1
        break
      fi
    done < vol_check.cfg
    sleep 2
  done

  # Set VNF_ID to 0 to take care of restart of Instance ...(why??)
  $CONTROLLER_CMD "sed -i -e '/$vol_name/c\\$vol_name\ 0' CFW_NFV_BASE_SUB_PATH/CFW_NFV_CONTROLLER_DIR/NFV/volume_check.cfg"
  LOG "volume attached!!!"
  sleep 5

  mkdir -p /opt/cfw

  ##############################################################################
  # MOUNT openstack volume to /opt/cfw/. If required format the volumne, make  #
  # an entry in fstab (/etc/fstab)                                             #
  ##############################################################################
  attach_host=$($CONTROLLER_CMD ". CFW_NFV_BASE_SUB_PATH/SOURCE_FILE; openstack volume show $vol_name | grep $VNF_ID")
  touch test
  echo "" > test

  value=$(echo $attach_host | cut -d ',' -f 1)
  i=2
  while [ ! -z "$value" ]
  do
    value=$(echo $attach_host | cut -d ',' -f $i)
    echo "$value" >> test
    echo "$value"
    ((i=i+1))
  done

  dev_name=$(grep device test | cut  -d ":" -f 2 | cut -d "'" -f 2)
  dev_check="$dev_name "
  LOG "device name: $dev_name"

  LOG "mounting $dev_name to /opt/cfw"
  mount -t ext4 $dev_name /opt/cfw > /dev/null 2>&1

  if grep $dev_check /proc/mounts; then
    LOG "device '$dev_name' is mounted.";
  else
    mkfs -t ext4 $dev_name > /dev/null 2>&1
    LOG "formatted the device '$dev_name'!"
    mount -t ext4 $dev_name /opt/cfw > /dev/null 2>&1
    LOG "mounted the device '$dev_name'!"
  fi


  BLK_ID=$(blkid | grep $dev_name | cut -d " " -f 2 | tr -d \")
  if grep "/opt/cfw" /etc/fstab > /dev/null 2>&1; then
    LOG "/opt/cfw entry already there in /etc/fstab."
  else
    LOG "adding /opt/cfw to /etc/fstab."
    echo "$BLK_ID       /opt/cfw     ext4    defaults     1       1" >> /etc/fstab
  fi
else
  BLOCK
  LOG "/opt/cfw already mounted"
fi


################################################################################
# Check /opt/cfw mount status, remount in rw, if necessary                     #
################################################################################
BLOCK
LOG "checking mount status.."
mount_status=`mount | grep /opt/cfw | grep rw`

if [ "$mount_status" == "" ]; then
  dev_name=$(grep device test | cut  -d ":" -f 2 | cut -d "'" -f 2)
  LOG "/opt/cfw is in 'ro' state, changing it to 'rw'"
  umount /opt/cfw > /dev/null 2>&1
  mount -t ext4 $dev_name /opt/cfw > /dev/null 2>&1
else
  LOG "/opt/cfw is in 'rw' state"
  mount | grep /opt/cfw
fi


################################################################################
# Create SNMP and EventHandler related directory in mounted volume.            #
################################################################################
LOG "creating required dirs in /opt/cfw/"
mkdir -p /opt/cfw
mkdir -p /opt/cfw/snmp
mkdir -p /opt/cfw/eventhandler


################################################################################
# To get VM instance name run this command in compute                          #
################################################################################
instance_name=$($CONTROLLER_CMD ". CFW_NFV_BASE_SUB_PATH/SOURCE_FILE; nova list --all --fields=instance_name,networks | grep -iw CFW_NODE1_PHYSICAL_IPV4 | awk '{print \$4}'")
instance_name=${instance_name// /}
$COMPUTE_CMD "rm -rf CFW_NFV_COMPUTE_SUB_PATH/CFW_NFV_COMPUTE_DIR" > /dev/null 2>&1
$COMPUTE_CMD "mkdir -p CFW_NFV_COMPUTE_SUB_PATH/CFW_NFV_COMPUTE_DIR"
LOG "================================="
LOG "vm instance name = $instance_name"
LOG "================================="


################################################################################
# Prepare SNMP node related informations. Here we update node type, device name#
# region and IP address.                                                       #
################################################################################
BLOCK
LOG "prepare snmp node informations -"
rm -f /etc/snmp_info > /dev/null 2>&1
touch /etc/snmp_info

echo "NODETYPE=CFW_NFV_VM_NODE_TYPE"      >> /etc/snmp_info
echo "DEVICENAME=CFW_NFV_VM_DEVICE_NAME"  >> /etc/snmp_info
echo "REGIONNAME=CFW_NFV_VM_REGION_NAME"  >> /etc/snmp_info
echo "MYIP=CFW_NODE1_PHYSICAL_IPV4"       >> /etc/snmp_info
echo "MYIPV6=CFW_NFV_VM_MY_IPV6"         >> /etc/snmp_info
echo "PEERIPV6=CFW_NFV_VM_PEER_IPV6"         >> /etc/snmp_info
echo "GEOSITETYPE=CFW_NFV_VM_GEOSITE_TYPE"         >> /etc/snmp_info
echo "PEERHOSTNAME=CFW_NFV_VM_PEER_HOST_NAME"         >> /etc/snmp_info
echo "SELFHOSTNAME=CFW_NFV_VM_SELF_HOST_NAME"         >> /etc/snmp_info
echo "DPCHAINID=CFW_NFV_VM_DP_CHAIN_ID"   >> /etc/snmp_info
echo "PEERIP=CFW_HA_PEER_PHYSICAL_IPV4"   >> /etc/snmp_info
echo "VIP=CFW_NODE1_VIRTUAL_IPV4"         >> /etc/snmp_info
echo "PR1IP=CFW_NFV_VM_PR1_IPV4"         >> /etc/snmp_info
echo "PR2IP=CFW_NFV_VM_PR2_IPV4"         >> /etc/snmp_info
echo "GR1IP=CFW_NFV_VM_GR1_IPV4"         >> /etc/snmp_info
echo "GR2IP=CFW_NFV_VM_GR2_IPV4"         >> /etc/snmp_info


LOG "populated /etc/snmp_info with following information"
LOG "NODETYPE=CFW_NFV_VM_NODE_TYPE"
LOG "DEVICENAME=CFW_NFV_VM_DEVICE_NAME"
LOG "REGIONNAME=CFW_NFV_VM_REGION_NAME"
LOG "MYIP=CFW_NODE1_PHYSICAL_IPV4"
LOG "MYIPV6=CFW_NFV_VM_MY_IPV6"
LOG "PEERIPV6=CFW_NFV_VM_PEER_IPV6"
LOG "GEOSITETYPE=CFW_NFV_VM_GEOSITE_TYPE"
LOG "PEERHOSTNAME=CFW_NFV_VM_PEER_HOST_NAME"
LOG "SELFHOSTNAME=CFW_NFV_VM_SELF_HOST_NAME"
LOG "DPCHAINID=CFW_NFV_VM_DP_CHAIN_ID"
LOG "PEERIP=CFW_HA_PEER_PHYSICAL_IPV4"
LOG "VIP=CFW_NODE1_VIRTUAL_IPV4"
LOG "PR1IP=CFW_NFV_VM_PR1_IPV4"
LOG "PR2IP=CFW_NFV_VM_PR2_IPV4"
LOG "GR1IP=CFW_NFV_VM_GR1_IPV4"
LOG "GR2IP=CFW_NFV_VM_GR2_IPV4"


################################################################################
# Process parameters from wigw_config.cfg file                                 #
################################################################################
BLOCK
LOG "attaching VF, It will take time so kindly wait!"
VMSLOTID=13
mapping_file="/opt/snic/bf_port_mapping"
BF_MAPPING=$($COMPUTE_CMD "cat $mapping_file")

if [ $? != 0 ]; then
  LOG "mapping file $mapping_file not found in compute node"
  LOG "need to update compute node with latest cloud os release"
  LOG "exiting ..."
  exit
fi

LOG "bf_port_mapping -"
LOG "$BF_MAPPING"

i=0
while IFS=' ' read -r line;
do {
  vf_config_found=0
  cpu_config=0;
  numa_config=0;

  ##############################################################################
  # Handle PF -- VF Configuration Mapping                                      #
  ##############################################################################
  if [[ "$line" == "PF"* ]]; then
    read -a strarr <<<"$line"
    PFID=${strarr[0]}
    VFID=${strarr[1]}
    PFID=${PFID#"PF"}
    PFID=${PFID%"VF"}
    vf_config_found=1
  fi


  if [[ $vf_config_found -eq 1 && $i -lt TOTAL_VF ]]; then
    PF_MLX_DEV=$($COMPUTE_CMD "cat $mapping_file|grep PF$PFID|cut -d':' -f 2")
    LOG "attaching PF$PFID VF$VFID to instance $instance_name"
    VFID=${VFID// /}
    pci_slot_name=$($COMPUTE_CMD "cat /sys/class/infiniband/$PF_MLX_DEV/device/virtfn$VFID/uevent | grep -i PCI_SLOT_NAME")
    pci_slot_name=${pci_slot_name// /}

    BUSID=$(echo  $pci_slot_name | cut -d ':' -f 2)
    SLOTID=$(echo $pci_slot_name | cut -d ':' -f 3 | cut -d '.' -f 1)
    FUNCID=$(echo $pci_slot_name | cut -d ':' -f 3 | cut -d '.' -f 2)
    PHY_IF=$((PFID+1))
    VMSLOTID=$((VMSLOTID+1))

    $COMPUTE_CMD "
    cat > CFW_NFV_COMPUTE_SUB_PATH/CFW_NFV_COMPUTE_DIR/compute_${instance_name}_pf_${PHY_IF}_vf_${VFID}.xml << EOF
   <hostdev mode='subsystem' type='pci' managed='yes'>
      <driver name='vfio'/>
      <source>
        <address domain=\"0x0000\" bus=\"0x$BUSID\" slot=\"0x$SLOTID\" function=\"0x$FUNCID\"/>
      </source>
      <address type='pci' domain='0x0000' bus='0x00' slot=\"0x$VMSLOTID\" function='0x0'/>
    </hostdev>
EOF" < /dev/null


    if $COMPUTE_CMD "LIBVIRT_DEFAULT_URI=qemu:///system virsh attach-device $instance_name CFW_NFV_COMPUTE_SUB_PATH/CFW_NFV_COMPUTE_DIR/compute_${instance_name}_pf_${PHY_IF}_vf_${VFID}.xml --persistent" > /dev/null 2>&1; then
      LOG "vf attachment successful!"
      i=$(($i+1))
    else
      if $COMPUTE_CMD "LIBVIRT_DEFAULT_URI=qemu:///system virsh attach-device $instance_name CFW_NFV_COMPUTE_SUB_PATH/CFW_NFV_COMPUTE_DIR/compute_${instance_name}_pf_${PHY_IF}_vf_${VFID}.xml --persistent 2>&1 | grep -i 'device is already in the domain configuration'" > /dev/null 2>&1; then
        LOG "this vf is already attached in this domain!"
        i=$(($i+1))
      else
        LOG "this vf is already used by other instance, try relaunching VNF with a different VF number!"
        LOG "exiting ..."
        exit
      fi
    fi

    if [ $i -eq TOTAL_VF ]; then
      LOG "all VFs attached successfully!"
    fi
  fi


  ##############################################################################
  # Handle CPU pinning configuration, We have to check with "CPU"* only. If we #
  # put "CPU PIN" then this will be replaced with value by replacevar.sh       #
  ##############################################################################
  if [[ "$line" == "CPU"* ]]; then
    read -a strarr <<<"$line"
    GUESTCPUID=${strarr[1]}
    HOSTCPUID=${strarr[2]}
    cpu_config=1
  fi
  
  if [ $cpu_config -eq 1 ]; then
    GUESTCPUID=${GUESTCPUID// /}
    HOSTCPUID=${HOSTCPUID// /}
  
    $COMPUTE_CMD "LIBVIRT_DEFAULT_URI=qemu:///system virsh vcpupin $instance_name $GUESTCPUID $HOSTCPUID"< /dev/null
    if [ $? == 0 ]; then
      LOG "CPU pinning for guest cpu $GUESTCPUID to Host cpu $HOSTCPUID successful!"
    else
      LOG "failed to pin guest cpu $GUESTCPUID to host cpu $HOSTCPUID!"
    fi
  fi
} </dev/null
done < /root/wigw_config.cfg


################################################################################
# Delete default route and check for any existing configuration, then load the #
# existing configuration.                                                               #
################################################################################
mgmt_dev=eth0

BLOCK

LOG "deleting default route entry for $mgmt_dev"
ip route delete default dev $mgmt_dev > /dev/null 2<&1
ip route delete default dev $mgmt_dev > /dev/null 2<&1
ip -6 route delete default dev $mgmt_dev > /dev/null 2<&1
echo 0 > /proc/sys/net/ipv6/conf/all/accept_ra_defrtr > /dev/null 2<&1
echo 0 > /proc/sys/net/ipv6/conf/$mgmt_dev/accept_ra_defrtr > /dev/null 2<&1


LOG "restarting dataplane service"
systemctl restart cfw-dataplane.service

if [ -f /opt/cfw/config.boot ]; then
  ##########################################################################
  # Load configuration, delete DHCP configuration for managemnet interface #
  ##########################################################################
  LOG "found a configuration in /opt/cfw/"
  cp /opt/cfw/snmp/snmpd.conf /opt/cfw/snmpd.conf > /dev/null 2>&1

  md5sum_local=`/usr/bin/md5sum /config/config.boot | cut -d " " -f 1`
  md5sum_sync=`/usr/bin/md5sum /opt/cfw/config.boot | cut -d " " -f 1`

  if [ "$md5sum_local" != "$md5sum_sync" ]; then
  	cp /opt/cfw/config.boot /opt/cfw/config_bk.boot > /dev/null 2>&1

  	LOG "loading configurations .."
  	LOG "load default configuration"
  	/opt/vyatta/sbin/lu -user configd -- /bin/vcli > /dev/null <<"EOF"
  	configure
  	load /opt/vyatta/etc/config.boot.default
  	commit
  	end_configure
EOF

  	LOG "load previously saved configuration"
  	cp /opt/cfw/snmpd.conf /opt/cfw/snmp/snmpd.conf > /dev/null 2>&1
  	/opt/vyatta/sbin/lu -user configd -- /bin/vcli > /dev/null <<"EOF"
  	configure
  	load /opt/cfw/config_bk.boot
  	commit
  	end_configure
EOF
  fi
fi

  ############################################################################
  # Launch auto config scripts.                                              #
  ############################################################################
  BLOCK
  if [ ! -f $AUTOCONFIG_DONE ]; then
    LOG "launching auto config"
    nodetype=CFW_NFV_VM_NODE_TYPE
    if [ "$nodetype" == "EPDGDP" ]; then
      echo "Node is EPDGDP, running auto-config for EPDGDP"
      python3 auto_config.py cloud epdgdp
    else
      echo "Node is $nodetype, running auto-config for TWAGDP"
      python3 auto_config.py cloud twagdp
    fi
    touch $AUTOCONFIG_DONE
  else
    LOG "auto_config was already executed"
  fi
  LOG "we are done!"
