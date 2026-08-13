#!/bin/bash

ConfigFile=$1
NS=cfw
JSONFile=$4
FLAVOR=$5
MYVNF=$7
DUPLICATE_VNF_NAME=$8
#List of Control Plane and Data Plane Nodes
declare -A ips=( [firewall_node10_IP1]="CFW_NODE1_PHYSICAL_IPV4" [firewall_node10_IP2]="ctrl-ipv4")
declare -A netname=( [nwkName1]="NETWORK_NAME" [nwkName2]="NETWORK_CONTROL_NAME")
mynets=("nwkName1" "nwkName2")

# Get the list of VNFs for which the yaml has to be generated
mapfile -t arr < <(cat $JSONFile | jq -r 'keys' | tr -d \" | tr -d \, | tr -d \ | tr -d \[ | tr -d \])

populate_json() {
    echo -e "##  Populating the ${GREEN}$JSONFile${NC} file from input cfg  ##"
    # Common Parameters getting from config file
    Image_name=$(awk '/CFW_IMAGE_NAME/{print $NF}' $ConfigFile)
    #echo $Image_name
    Controller_User=$(awk '/CONTROLLER_USER/{print $NF}' $ConfigFile)
    CONTROLLER_IP=$(awk '/CONTROLLER_IP/{print $NF}' $ConfigFile)
    #echo $CONTROLLER_IP
    CONTROLLER_PASSWORD=$(awk '/CONTROLLER_PASSWORD/{print $NF}' $ConfigFile)
    HNAME=$(awk '/CFW_NAME_NODE/{print $NF}' $ConfigFile)
    PROVIDER_NAME=$(awk '/NETWORK_NAME/{print $NF}' $ConfigFile)
    PROVIDER_HA_NAME=$(awk '/NETWORK_HA_NAME/{print $NF}' $ConfigFile)
    ADDRPAIR="0.0.0.0/0" #$(awk '/SUBNET/{print $NF}' $ConfigFile)

    CFW_NFV_BASE_SUB_PATH=$(awk '/CFW_NFV_BASE_SUB_PATH/{print $NF}' $ConfigFile)
    CFW_NFV_CONTROLLER_DIR=$(awk '/CFW_NFV_CONTROLLER_DIR/{print $NF}' $ConfigFile)
    ENV_FILE_NAME=$(awk '/SOURCE_FILE/{print $NF}' $ConfigFile)
    # Controller_User=${Controller_User//$'\n'/}
    
    #Nodes Flavor getting from config file
    CFW_vcpu_count=$(awk '/CFW_VCPUCOUNT/{print $NF}' $FLAVOR)
    #echo $HSS_vcpu_count
    CFW_memorymb=$(awk '/CFW_MEMORYGB/{print $NF}' $FLAVOR)
    #echo $HSS_memorymb
    CFW_storagegb=$(awk '/CFW_STORAGEGB/{print $NF}' $FLAVOR)
    #echo $HSS_storagegb

    # Common Parameters populating into the JSON file
    sed -i '/myHostname/c\ \                "myHostname\" : \"'$HNAME'\",' $JSONFile
    sed -i '/CONTROLLER_IP/c\ \                       "CONTROLLER_IP\" : \"'$CONTROLLER_IP'\",' $JSONFile
    sed -i '/CONTROLLER_USER/c\ \                     "CONTROLLER_USER\" : \"'$Controller_User'\",' $JSONFile
    sed -i '/CONTROLLER_PASSWORD/c\ \                 "CONTROLLER_PASSWORD\" : \"'$CONTROLLER_PASSWORD'\",' $JSONFile
    sed -i '/CFW_NFV_BASE_SUB_PATH/c\ \               "CFW_NFV_BASE_SUB_PATH\" : \"'$CFW_NFV_BASE_SUB_PATH'\",' $JSONFile
    sed -i '/CFW_NFV_CONTROLLER_DIR/c\ \               "CFW_NFV_CONTROLLER_DIR\" : \"'$CFW_NFV_CONTROLLER_DIR'\",' $JSONFile
    sed -i '/ADDRPAIR/c\ \                       "ADDRPAIR\" : \"'$ADDRPAIR'\",' $JSONFile
    sed -i '/USER_ENV/c\ \                       "USER_ENV\" : \"'$CFW_NFV_BASE_SUB_PATH/$ENV_FILE_NAME'\",' $JSONFile
    sed -i '/imageName/c\ \                           "imageName\" : \"'$Image_name'\",' $JSONFile
    #sed -i '/nwkName1/c\ \                             "nwkName1\" : \"'$PROVIDER_NAME'\",' $JSONFile
    #sed -i '/nwkName2/c\ \                             "nwkName2\" : \"'$PROVIDER_HA_NAME'\"' $JSONFile
    #Nodes Flavor populating into the JSON file
    sed -i '/vcpuCount/c\ \                          "vcpuCount\" : \"'$CFW_vcpu_count'\",' $JSONFile
    sed -i '/memoryMb/c\ \                    "memoryMb\" : \"'$CFW_memorymb'\",' $JSONFile
    sed -i '/storageGb/c\ \                   "storageGb\" : \"'$CFW_storagegb'\"' $JSONFile

    # VNF Ip address (Unique Parameters) getting from config file and populating into the JSON File
    #for nodeip in ${myarr[@]}; do
        #echo $nodeip
        #myip=$(grep -r $nodeip $ConfigFile | awk '{print $2}' |head -1)
        #echo $myip
        #sed -i '/'$nodeip'/c\ \                       "'$nodeip'\" : \"'$myip'\",' $JSONFile
        #perl -p -i -e "s/\r//g" $JSONFile
    #done

    perl -p -i -e "s/\r//g" $JSONFile
}
  
generate_vnfds(){
    	echo -e "##  Generating the ${GREEN} OSM VNFD${NC} Packages  ##\n"
    	# Replacing the values in userdata first
	t=$(echo $3 | awk '{print $2}')
	echo $t
	cp $2 ${t}_vnfd.yaml
        # sed "s/=/ /g" $ConfigFile >sed_temp.txt
        # cat sed_temp.txt
	# while read -r key value
	# do
	#   if [[ $key != \#* ]]; then
	#       echo "s;$key;$value;g" >> sedtmpfile
        #   fi
	# done < sed_temp.txt
	# /bin/rm -f sed_temp.txt
	# sed -i "/\;\;g/d" sedtmpfile
	# #perl -p -i -e "s/\r//g" sedtmpfile
    	# sed -f sedtmpfile $2  > ${t}_vnfd.yaml
	# /bin/rm -f sedtmpfile
	read genFlag < <(cat $JSONFile | jq .$t.vnf.genFlag | tr -d \")
        if [ $genFlag == 'On' ]; then
                echo "Converting for VNF element $t"
                read vnfid < <(cat $JSONFile | jq .$t.vnf.vnfid | tr -d \")
                read vnfName < <(cat $JSONFile | jq .$t.vnf.vnfName | tr -d \")
                read vnfShortName < <(cat $JSONFile | jq .$t.vnf.vnfShortName | tr -d \")
                read vnfDesc < <(cat $JSONFile | jq .$t.vnf.vnfDesc | tr -d \")
                read vduid < <(cat $JSONFile | jq .$t.vnf.vduid | tr -d \")
                read vduName < <(cat $JSONFile | jq .$t.vnf.vduName | tr -d \")
                read vduDesc < <(cat $JSONFile | jq .$t.vnf.vduDesc | tr -d \")
                read imageName < <(cat $JSONFile | jq .$t.vnf.imageName | tr -d \")
                read myVNF < <(cat $JSONFile | jq .$t.vnf.myVNF | tr -d \")
                read vcpuCount < <(cat $JSONFile | jq .$t.vnf.vmFlavour.vcpuCount | tr -d \")
                read  memoryMb < <(cat $JSONFile | jq .$t.vnf.vmFlavour.memoryMb | tr -d \")
                read storageGb < <(cat $JSONFile | jq .$t.vnf.vmFlavour.storageGb | tr -d \")
                read myHostname < <(cat $JSONFile | jq .$t.vnf.myHostname | tr -d \")
                read CONTROLLER_IP < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_IP | tr -d \")
                read CONTROLLER_USER < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_USER | tr -d \")
                read CONTROLLER_PASSWORD < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_PASSWORD | tr -d \")
		read CFW_NFV_BASE_SUB_PATH < <(cat $JSONFile | jq .$t.vnf.CFW_NFV_BASE_SUB_PATH | tr -d \")
                read CFW_NFV_CONTROLLER_DIR < <(cat $JSONFile | jq .$t.vnf.CFW_NFV_CONTROLLER_DIR | tr -d \")
		#read ADDRPAIR < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \")
		read ADDRPAIR < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \" | awk -F"/"  '{print $1}')
                read SUBLEN < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \" | awk -F"/"  '{print $2}')
		read USER_ENV < <(cat $JSONFile | jq .$t.vnf.USER_ENV | tr -d \")
                sed -i "s/vnfid/$vnfid/g" ${t}_vnfd.yaml
                sed -i "s/vnfName/$vnfName/g" ${t}_vnfd.yaml
                sed -i "s/vnfShortName/$vnfShortName/g" ${t}_vnfd.yaml
                sed -i "s/vnfDesc/$vnfDesc/g" ${t}_vnfd.yaml
                sed -i "s/vduid/$vduid/g" ${t}_vnfd.yaml
                sed -i "s/vduName/$vduName/g" ${t}_vnfd.yaml
                sed -i "s/vduDesc/$vduDesc/g" ${t}_vnfd.yaml
                sed -i "s/imageName/$imageName/g" ${t}_vnfd.yaml
                sed -i "s/vx/$vcpuCount/g" ${t}_vnfd.yaml
                sed -i "s/mx/$memoryMb/g" ${t}_vnfd.yaml
                sed -i "s/sx/$storageGb/g" ${t}_vnfd.yaml
                sed -i "s/myHostname/$myHostname/g" ${t}_vnfd.yaml
                sed -i "s/myVNF/$myVNF/g" ${t}_vnfd.yaml
                sed -i "s/CONTROLLER_IP/$CONTROLLER_IP/g" ${t}_vnfd.yaml
                sed -i "s/CONTROLLER_USER/$CONTROLLER_USER/g" ${t}_vnfd.yaml
                sed -i "s/CONTROLLER_PASSWORD/$CONTROLLER_PASSWORD/g" ${t}_vnfd.yaml
		sed -i "s#CFW_NFV_BASE_SUB_PATH#$CFW_NFV_BASE_SUB_PATH#g" ${t}_vnfd.yaml
                sed -i "s#CFW_NFV_CONTROLLER_DIR#$CFW_NFV_CONTROLLER_DIR#g" ${t}_vnfd.yaml
		sed -i "s#ADDRPAIR#$ADDRPAIR#g" ${t}_vnfd.yaml
		sed -i "s#SUBLEN#$SUBLEN#g" ${t}_vnfd.yaml
		sed -i "s#USER_ENV#$USER_ENV#g" ${t}_vnfd.yaml
		autohealid=$vduid'_'autoheal
                sed -i "s/autohealid/$autohealid/g" ${t}_vnfd.yaml
                if [ -n "$DUPLICATE_VNF_NAME" ]; then
                	sed -i "s/$MYVNF/$DUPLICATE_VNF_NAME/g" ${t}_vnfd.yaml
			mv ${t}_vnfd.yaml ${DUPLICATE_VNF_NAME}_vnfd.yaml
                	mkdir $DUPLICATE_VNF_NAME'_vnf'; mv ${DUPLICATE_VNF_NAME}_vnfd.yaml $DUPLICATE_VNF_NAME'_vnf'
			tar -czvf $DUPLICATE_VNF_NAME'_vnf.tar.gz' $DUPLICATE_VNF_NAME'_vnf'
		else
			mkdir $t'_vnf'; mv ${t}_vnfd.yaml $t'_vnf'
                        tar -czvf $t'_vnf.tar.gz' $t'_vnf'
		fi
        fi
    #done
}

generate_ns_param(){
    echo -e "##  Generating the ${GREEN} OSM NSD${NC} Packages  ##\n"
    t=$(echo $3 | awk '{print $2}')
    echo $t
    ha_mode=$(awk '/CFW_HA_MODE/{print $NF}' $ConfigFile)
    echo $ha_mode
    #if [[ $ha_mode == 0 ]];then
        #sed -i '/name: mgmt2/,$d' $2
    #fi
    for key in ${!ips[@]}; do
        read myip < <(cat $JSONFile | jq .$t.ns.$key | tr -d \")	
	#sed -i "s/$key/$myip/g" $2;
	#if [[ ! -z "$myip" ]] && echo "Not empty" || echo "Empty" ; then
	if [[ $myip != "null" ]]; then
      		# echo $key $myip
		sed -i "s/$key/$myip/g" $2;
        fi
    done

    for key in ${!netname[@]}; do
	read mynwk < <(cat $JSONFile | jq .$t.ns.$key | tr -d \")
	if [[ $mynwk != "null" ]]; then
		#echo $key $mynwk
		sed -i "s/$key/$mynwk/g" $2;
	fi
    done
    sed -i "s/${MYVNF}_vnfd/${DUPLICATE_VNF_NAME}_vnfd/" $2;
}

if [[ $6 == "PARAM" ]]; then
        populate_json
        #generate_ns_param $JSONFile $3

elif [[ $6 == VNFD* ]]; then
        #populate_json
        generate_vnfds $JSONFile $2 "$6"
else
        #populate_json
        #generate_vnfds $JSONFile $2 "$6"
        generate_ns_param $JSONFile $3 "$6"
fi

