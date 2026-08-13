#!/bin/bash
ConfigFile=$1
NS=epc
JSONFile=$4
FLAVOR=$5

#List of Control Plane and Data Plane Nodes

while read -r key value
  do
    if [ "$key" == "SGW_TOTAL_NUM_NODES_CP_AND_DP" ] ; then
      #num_sgw_dp=`expr $value - 2`
      num_sgw_dp=$(echo $value-2 | tr -d $'\r' | bc)
    fi
    if [ "$key" == "PGW_TOTAL_NUM_NODES_CP_AND_DP" ] ; then
      #num_pgw_dp=`expr $value - 2`
      num_pgw_dp=$(echo $value-2 | tr -d $'\r' | bc)
    fi
    if [ "$key" == "EPC_CONTEXT_NAME" ]; then
       CONTEXT=$(echo $value | tr -d $'\r')
    fi

  done < $ConfigFile

declare -A ips=( [pcrf_cp_node1_IP1]="PCRF_NODE1_PHYSICAL_IPV4" [mme_cp_node1_IP1]="MME_NODE1_PHYSICAL_IPV4" [sgw_cp_node1_IP1]="SGW_NODE1_PHYSICAL_IPV4" [pgw_cp_node1_IP1]="PGW_NODE1_PHYSICAL_IPV4" [pcrf_cp_node2_IP1]="PCRF_NODE2_PHYSICAL_IPV4" [mme_cp_node2_IP1]="MME_NODE2_PHYSICAL_IPV4" [sgw_cp_node2_IP1]="SGW_NODE2_PHYSICAL_IPV4" [pgw_cp_node2_IP1]="PGW_NODE2_PHYSICAL_IPV4" [pgw_dp_node1_IP1]="PGW_NODE3_PHYSICAL_IPV4" [sgw_dp_node1_IP1]="SGW_NODE3_PHYSICAL_IPV4" [pgw_dp_node2_IP1]="PGW_NODE4_PHYSICAL_IPV4" [sgw_dp_node2_IP1]="SGW_NODE4_PHYSICAL_IPV4" [tce_node1]="TCE_NODE_PHYSICAL_IPV4" )

declare -A ip6s=( [pcrf_cp_node1_V6IP1]="PCRF_NODE1_PHYSICAL_IPV6" [mme_cp_node1_V6IP1]="MME_NODE1_PHYSICAL_IPV6" [sgw_cp_node1_V6IP1]="SGW_NODE1_PHYSICAL_IPV6" [pgw_cp_node1_V6IP1]="PGW_NODE1_PHYSICAL_IPV6" [pcrf_cp_node2_V6IP1]="PCRF_NODE2_PHYSICAL_IPV6" [mme_cp_node2_V6IP1]="MME_NODE2_PHYSICAL_IPV6" [sgw_cp_node2_V6IP1]="SGW_NODE2_PHYSICAL_IPV6" [pgw_cp_node2_V6IP1]="PGW_NODE2_PHYSICAL_IPV6" [pgw_dp_node1_V6IP1]="PGW_NODE3_PHYSICAL_IPV6" [sgw_dp_node1_V6IP1]="SGW_NODE3_PHYSICAL_IPV6" [pgw_dp_node2_V6IP1]="PGW_NODE4_PHYSICAL_IPV6" [sgw_dp_node2_V6IP1]="SGW_NODE4_PHYSICAL_IPV6" [tce_node1]="TCE_NODE_PHYSICAL_IPV6" )

declare -A netname=( [nwkName1]="PROVIDER_NAME" [nwkName2]="PROVIDER_DP_NAME")
mynets=("nwkName1" "nwkName2")

myarr=(PCRF_NODE1_PHYSICAL_IPV4 MME_NODE1_PHYSICAL_IPV4 SGW_NODE1_PHYSICAL_IPV4 PGW_NODE1_PHYSICAL_IPV4 PCRF_NODE2_PHYSICAL_IPV4 MME_NODE2_PHYSICAL_IPV4 SGW_NODE2_PHYSICAL_IPV4 PGW_NODE2_PHYSICAL_IPV4 PGW_NODE3_PHYSICAL_IPV4 SGW_NODE3_PHYSICAL_IPV4 PGW_NODE4_PHYSICAL_IPV4 SGW_NODE4_PHYSICAL_IPV4 TCE_NODE_PHYSICAL_IPV4)

myarr1=(PCRF_NODE1_PHYSICAL_IPV6 MME_NODE1_PHYSICAL_IPV6 SGW_NODE1_PHYSICAL_IPV6 PGW_NODE1_PHYSICAL_IPV6 PCRF_NODE2_PHYSICAL_IPV6 MME_NODE2_PHYSICAL_IPV6 SGW_NODE2_PHYSICAL_IPV6 PGW_NODE2_PHYSICAL_IPV6 PGW_NODE3_PHYSICAL_IPV6 SGW_NODE3_PHYSICAL_IPV6 PGW_NODE4_PHYSICAL_IPV6 SGW_NODE4_PHYSICAL_IPV6 TCE_NODE_PHYSICAL_IPV6)

if [[ "$num_sgw_dp" -gt "1" ]]; then
        for i in $(seq 2 $num_sgw_dp);do
                node_num=$(expr $i + 2)
                myarr+=('SGW_NODE'$node_num'_PHYSICAL_IPV4')
                myarr1+=('SGW_NODE'$node_num'_PHYSICAL_IPV6')
		#echo $myarr1
        done
fi
if [[ "$num_pgw_dp" -gt "1" ]]; then
        for i in $(seq 2 $num_pgw_dp);do
                node_num=$(expr $i + 2)
                myarr+=('PGW_NODE'$node_num'_PHYSICAL_IPV4')
                myarr1+=('PGW_NODE'$node_num'_PHYSICAL_IPV6')
		#echo $myarr1
        done
fi

# Get the list of VNFs for which the yaml has to be generated
mapfile -t arr < <(cat $JSONFile | jq -r 'keys' | tr -d \" | tr -d \, | tr -d \ | tr -d \[ | tr -d \]) 

populate_json() {
    # Common Parameters getting from config file
    echo -e "##  Populating the ${GREEN}$JSONFile${NC} file from input cfg  ##\n"
    Image_name=$(awk '/IMAGE_NAME/{print $NF}' $ConfigFile)
    Image_fp_name=$(awk '/IMAGE_FPDP_NAME/{print $NF}' $ConfigFile)
    Controller_User=$(awk '/CONTROLLER_USER/{print $NF}' $ConfigFile)
    CONTROLLER_IP=$(awk '/CONTROLLER_IP/{print $NF}' $ConfigFile)
    CONTROLLER_PASSWORD=$(awk '/CONTROLLER_PASSWORD/{print $NF}' $ConfigFile)
    EPC_NFV_BASE_SUB_PATH=$(awk '/EPC_NFV_BASE_SUB_PATH/{print $NF}' $ConfigFile)
    ENV_FILE_NAME=$(awk '/SOURCE_FILE/{print $NF}' $ConfigFile)

    #PREFIX len
    MME_NODE_IP_PREFIX=$(awk '/MME_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    MME_NODE_IP_PREFIXLEN=$(awk '/MME_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    SGW_NODE_IP_PREFIX=$(awk '/SGW_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    SGW_NODE_IP_PREFIXLEN=$(awk '/SGW_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    PGW_NODE_IP_PREFIX=$(awk '/PGW_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    PGW_NODE_IP_PREFIXLEN=$(awk '/PGW_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    PCRF_NODE_IP_PREFIX=$(awk '/PCRF_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    PCRF_NODE_IP_PREFIXLEN=$(awk '/PCRF_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    echo "-------------------------------"
    echo $PCRF_NODE_IP_PREFIXLEN
    TCE_NODE_IP_PREFIX=$(awk '/TCE_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    TCE_NODE_IP_PREFIXLEN=$(awk '/TCE_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    SGW_DP_NODE_IP_PREFIX=$(awk '/SGW_DP_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    SGW_DP_NODE_IP_PREFIXLEN=$(awk '/SGW_DP_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    PGW_DP_NODE_IP_PREFIX=$(awk '/PGW_DP_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    PGW_DP_NODE_IP_PREFIXLEN=$(awk '/PGW_DP_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)

    HNAME=$(awk '/EPC_CONTEXT_NAME/{print $NF}' $ConfigFile)
    PROVIDER_NAME=$(awk '/NETWORK_NAME/{print $NF}' $ConfigFile)
    PROVIDER_DP_NAME=$(awk '/NETWORK_DP_NAME/{print $NF}' $ConfigFile)
    ADDRPAIR=$(awk '/EPC_NODE_IP_PREFIX/{print $NF}' $ConfigFile)
    SUBLEN=$(awk '/EPC_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    IPV6ADDRESS=$(awk '/EPC_NODE_IPV6_PREFIX/{print $NF}' $ConfigFile)
    echo $IPV6ADDRESS
    IPV6SUBLEN=$(awk '/EPC_NODEIPV6_PREFIXLEN/{print $NF}' $ConfigFile)
    echo $IPV6SUBLEN
    DPADDRPAIR=$(awk '/EPC_DP_NODE_IP_PREFIX /{print $NF}' $ConfigFile)  # Space is given here to differentiate prefix and prefixlen
    DPSUBLEN=$(awk '/EPC_DP_NODEIP_PREFIXLEN/{print $NF}' $ConfigFile)
    DPIPV6ADDRESS=$(awk '/EPC_DP_NODE_IPV6_PREFIX /{print $NF}' $ConfigFile)  # Space is given here to differentiate prefix and prefixlen
    echo $DPIPV6ADDRESS
    DPIPV6SUBLEN=$(awk '/EPC_DP_NODEIPV6_PREFIXLEN/{print $NF}' $ConfigFile) 
    echo $DPIPV6SUBLEN
    #Nodes Flavor getting from config file
    MME_vcpu_count=$(awk '/MME_VCPUCOUNT/{print $NF}' $FLAVOR)
    MME_memorymb=$(awk '/MME_MEMORYGB/{print $NF}' $FLAVOR)
    MME_storagegb=$(awk '/MME_STORAGEGB/{print $NF}' $FLAVOR)
    SGW_vcpu_count=$(awk '/SGW_VCPUCOUNT/{print $NF}' $FLAVOR)
    SGW_memorymb=$(awk '/SGW_MEMORYGB/{print $NF}' $FLAVOR)
    SGW_storagegb=$(awk '/SGW_STORAGEGB/{print $NF}' $FLAVOR)
    PGW_vcpu_count=$(awk '/PGW_VCPUCOUNT/{print $NF}' $FLAVOR)
    PGW_memorymb=$(awk '/PGW_MEMORYGB/{print $NF}' $FLAVOR)
    PGW_storagegb=$(awk '/PGW_STORAGEGB/{print $NF}' $FLAVOR)
    PCRF_vcpu_count=$(awk '/PCRF_VCPUCOUNT/{print $NF}' $FLAVOR)
    PCRF_memorymb=$(awk '/PCRF_MEMORYGB/{print $NF}' $FLAVOR)
    PCRF_storagegb=$(awk '/PCRF_STORAGEGB/{print $NF}' $FLAVOR)
    TCE_vcpu_count=$(awk '/TCE_VCPUCOUNT/{print $NF}' $FLAVOR)
    TCE_memorymb=$(awk '/TCE_MEMORYGB/{print $NF}' $FLAVOR)
    TCE_storagegb=$(awk '/TCE_STORAGEGB/{print $NF}' $FLAVOR)
    SGW_FP_vcpu_count=$(awk '/SGW_FP_VCPUCOUNT/{print $NF}' $FLAVOR)
    SGW_FP_memorymb=$(awk '/SGW_FP_MEMORYGB/{print $NF}' $FLAVOR)
    SGW_FP_storagegb=$(awk '/SGW_FP_STORAGEGB/{print $NF}' $FLAVOR)
    PGW_FP_vcpu_count=$(awk '/PGW_FP_VCPUCOUNT/{print $NF}' $FLAVOR)
    PGW_FP_memorymb=$(awk '/PGW_FP_MEMORYGB/{print $NF}' $FLAVOR)
    PGW_FP_storagegb=$(awk '/PGW_FP_STORAGEGB/{print $NF}' $FLAVOR)


    #prefix len
    sed -i '/PCRF_ADDRPAIR_CP/c\ \                 "PCRF_ADDRPAIR_CP\" : \"'$PCRF_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/MME_ADDRPAIR_CP/c\ \                 "MME_ADDRPAIR_CP\" : \"'$MME_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/SGW_ADDRPAIR_CP/c\ \                 "SGW_ADDRPAIR_CP\" : \"'$SGW_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/PGW_ADDRPAIR_CP/c\ \                 "PGW_ADDRPAIR_CP\" : \"'$PGW_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/TCE_ADDRPAIR_CP/c\ \                 "TCE_ADDRPAIR_CP\" : \"'$TCE_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/PGW_ADDRPAIR_DP/c\ \                 "PGW_ADDRPAIR_DP\" : \"'$PGW_DP_NODE_IP_PREFIX'\",' $JSONFile
    sed -i '/SGW_ADDRPAIR_DP/c\ \                 "SGW_ADDRPAIR_DP\" : \"'$SGW_DP_NODE_IP_PREFIX'\",' $JSONFile

    ##
    sed -i '/PCRF_SUBLEN_CP/c\ \                 "PCRF_SUBLEN_CP\" : \"'$PCRF_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/MME_SUBLEN_CP/c\ \                 "MME_SUBLEN_CP\" : \"'$MME_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/SGW_SUBLEN_CP/c\ \                 "SGW_SUBLEN_CP\" : \"'$SGW_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/PGW_SUBLEN_CP/c\ \                 "PGW_SUBLEN_CP\" : \"'$PGW_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/TCE_SUBLEN_CP/c\ \                 "TCE_SUBLEN_CP\" : \"'$TCE_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/PGW_SUBLEN_DP/c\ \                 "PGW_SUBLEN_DP\" : \"'$PGW_NODE_IP_PREFIXLEN'\",' $JSONFile
    sed -i '/SGW_SUBLEN_DP/c\ \                 "SGW_SUBLEN_DP\" : \"'$PCRF_NODE_IP_PREFIXLEN'\",' $JSONFile

    # Common Parameters populating into the JSON file
    sed -i '/EPC_CONTEXT_NAME/c\ \              "EPC_CONTEXT_NAME\" : \"'$HNAME'\",' $JSONFile
    sed -i '/CONTROLLER_IP/c\ \			"CONTROLLER_IP\" : \"'$CONTROLLER_IP'\",' $JSONFile    
    sed -i '/CONTROLLER_USER/c\ \			"CONTROLLER_USER\" : \"'$Controller_User'\",' $JSONFile
    sed -i '/CONTROLLER_PASSWORD/c\ \			"CONTROLLER_PASSWORD\" : \"'$CONTROLLER_PASSWORD'\",' $JSONFile    
    sed -i '/imageName/c\ \			"imageName\" : \"'$Image_name'\",' $JSONFile
    sed -i '/EPC_NFV_BASE_SUB_PATH/c\ \               "EPC_NFV_BASE_SUB_PATH\" : \"'$EPC_NFV_BASE_SUB_PATH'\",' $JSONFile
    sed -i '/USER_ENV/c\ \                       "USER_ENV\" : \"'/home/$Controller_User/$ENV_FILE_NAME'\",' $JSONFile
    sed -i '/HOME_ENV/c\ \                       "HOME_ENV\" : \"'/home/ubuntu/$ENV_FILE_NAME'\",' $JSONFile
    #sed -i '/ADDRPAIR_CP/c\ \                 "ADDRPAIR_CP\" : \"'$ADDRPAIR'\",' $JSONFile
    #sed -i '/SUBLEN_CP/c\ \                 "SUBLEN_CP\" : \"'$SUBLEN'\",' $JSONFile
    sed -i '/V6ADDRESS_CP/c\ \                 "V6ADDRESS_CP\" : \"'$IPV6ADDRESS'\",' $JSONFile
    sed -i '/SUBLENV6_CP/c\ \                 "SUBLENV6_CP\" : \"'$IPV6SUBLEN'\",' $JSONFile
    #sed -i '/nwkName_cp/c\ \                       "nwkName_cp\" : \"'$PROVIDER_NAME'\"' $JSONFile
    #sed -i '/nwkName_dp/c\ \                       "nwkName_dp\" : \"'$PROVIDER_DP_NAME'\"' $JSONFile
    #sed -i '/ADDRPAIR_DP/c\ \                 "ADDRPAIR_DP\" : \"'$DPADDRPAIR'\",' $JSONFile
    #sed -i '/SUBLEN_DP/c\ \                 "SUBLEN_DP\" : \"'$DPSUBLEN'\",' $JSONFile
    sed -i '/V6ADDRESS_DP/c\ \                 "V6ADDRESS_DP\" : \"'$DPIPV6ADDRESS'\",' $JSONFile
    sed -i '/SUBLENV6_DP/c\ \                 "SUBLENV6_DP\" : \"'$DPIPV6SUBLEN'\",' $JSONFile

    sed -i '/imagefpName/c\ \                     "imagefpName\" : \"'$Image_fp_name'\",' $JSONFile
    #Nodes Flavor populating into the JSON file
    sed -i '/pcrf_vcpuCount/c\ \			  "pcrf_vcpuCount\" : \"'$PCRF_vcpu_count'\",' $JSONFile
    sed -i '/pcrf_memoryMb/c\ \			   "pcrf_memoryMb\" : \"'$PCRF_memorymb'\",' $JSONFile
    sed -i '/pcrf_storageGb/c\ \			  "pcrf_storageGb\" : \"'$PCRF_storagegb'\"' $JSONFile
    sed -i '/mme_vcpuCount/c\ \			  "mme_vcpuCount\" : \"'$MME_vcpu_count'\",' $JSONFile
    sed -i '/mme_memoryMb/c\ \			   "mme_memoryMb\" : \"'$MME_memorymb'\",' $JSONFile
    sed -i '/mme_storageGb/c\ \			  "mme_storageGb\" : \"'$MME_storagegb'\"' $JSONFile
    sed -i '/sgw_vcpuCount/c\ \			  "sgw_vcpuCount\" : \"'$SGW_vcpu_count'\",' $JSONFile
    sed -i '/sgw_memoryMb/c\ \			   "sgw_memoryMb\" : \"'$SGW_memorymb'\",' $JSONFile
    sed -i '/sgw_storageGb/c\ \			  "sgw_storageGb\" : \"'$SGW_storagegb'\"' $JSONFile
    sed -i '/pgw_vcpuCount/c\ \			  "pgw_vcpuCount\" : \"'$PGW_vcpu_count'\",' $JSONFile
    sed -i '/pgw_memoryMb/c\ \			   "pgw_memoryMb\" : \"'$PGW_memorymb'\",' $JSONFile
    sed -i '/pgw_storageGb/c\ \			  "pgw_storageGb\" : \"'$PGW_storagegb'\"' $JSONFile
    sed -i '/tce_vcpuCount/c\ \                   "tce_vcpuCount\" : \"'$TCE_vcpu_count'\",' $JSONFile
    sed -i '/tce_memoryMb/c\ \                     "tce_memoryMb\" : \"'$TCE_memorymb'\",' $JSONFile
    sed -i '/tce_storageGb/c\ \                   "tce_storageGb\" : \"'$TCE_storagegb'\"' $JSONFile
    sed -i '/sgw_fp_vcpuCount/c\ \                   "sgw_fp_vcpuCount\" : \"'$SGW_FP_vcpu_count'\",' $JSONFile
    sed -i '/sgw_fp_memoryMb/c\ \                     "sgw_fp_memoryMb\" : \"'$SGW_FP_memorymb'\",' $JSONFile
    sed -i '/sgw_fp_storageGb/c\ \                   "sgw_fp_storageGb\" : \"'$SGW_FP_storagegb'\"' $JSONFile
    sed -i '/pgw_fp_vcpuCount/c\ \                   "pgw_fp_vcpuCount\" : \"'$PGW_FP_vcpu_count'\",' $JSONFile
    sed -i '/pgw_fp_memoryMb/c\ \                     "pgw_fp_memoryMb\" : \"'$PGW_FP_memorymb'\",' $JSONFile
    sed -i '/pgw_fp_storageGb/c\ \                   "pgw_fp_storageGb\" : \"'$PGW_FP_storagegb'\"' $JSONFile

    # VNF Ip address (Unique Parameters) getting from config file and populating into the JSON File
    for nodeip in ${myarr[@]}; do
        myip=$(grep -r $nodeip $ConfigFile | awk '{print $2}' |head -1)
        sed -i '/'$nodeip'/c\ \                       "'$nodeip'\" : \"'$myip'\",' $JSONFile
    done

    for nodeip in ${myarr1[@]}; do
        myip=$(grep -r $nodeip $ConfigFile | awk '{print $2}' |head -1)
        sed -i '/'$nodeip'/c\ \                       "'$nodeip'\" : \"'$myip'\",' $JSONFile
    done


    perl -p -i -e "s/\r//g" $JSONFile
}

generate_vnfds(){
    echo -e "##  Generating the ${GREEN} OSM VNFD${NC} Packages  ##"
    # Replacing the values in userdata first

    declare -A hostnames_array=( [sgw_cp_node1]="SGW-EPC_CONTEXT_NAME-1" [sgw_cp_node2]="SGW-EPC_CONTEXT_NAME-2" [mme_cp_node1]="MME-EPC_CONTEXT_NAME-1" [mme_cp_node2]="MME-EPC_CONTEXT_NAME-2" [pgw_cp_node1]="PGW-EPC_CONTEXT_NAME-1" [pgw_cp_node2]="PGW-EPC_CONTEXT_NAME-2" [pcrf_cp_node1]="PCRF-EPC_CONTEXT_NAME-1" [pcrf_cp_node2]="PCRF-EPC_CONTEXT_NAME-2" [sgw_dp_node1]="SGW-DP-EPC_CONTEXT_NAME-1" [pgw_dp_node1]="PGW-DP-EPC_CONTEXT_NAME-1" [tce_node1]="TCE-EPC_CONTEXT_NAME" [sgw_fp_dp_node1]="SGW-DP-EPC_CONTEXT_NAME-1" [pgw_fp_dp_node1]="PGW-DP-EPC_CONTEXT_NAME-1" )
    
    if [[ "$num_sgw_dp" -gt "1" ]]; then
        for i in $(seq 2 $num_sgw_dp);do
                hostnames_array+=( ["sgw_fp_dp_node"$i]="SGW-DP-EPC_CONTEXT_NAME-"$i ["sgw_dp_node"$i]="SGW-DP-EPC_CONTEXT_NAME-"$i)
        done
    fi
    if [[ "$num_pgw_dp" -gt "1" ]]; then
        for i in $(seq 2 $num_pgw_dp);do
                hostnames_array+=( ["pgw_fp_dp_node"$i]="PGW-DP-EPC_CONTEXT_NAME-"$i ["pgw_dp_node"$i]="PGW-DP-EPC_CONTEXT_NAME-"$i)
        done
    fi
    declare -A new_HA
    for key in ${!hostnames_array[@]}; do
	    match="_"
	    context=$CONTEXT

            if [ "$key" == "tce_node1" ] ; then              
                new_key=$(echo "$key" | sed "0,/$match/s/$match/&$context$match/")
            else
                new_key=$(echo "$key" | sed "s/\(cp\|dp\|fp_dp\)/&$match$context/")
            fi

	    new_HA[$new_key]=${hostnames_array[${key}]}
    done

    t=$(echo $3 | awk '{print $2}')
    cp $2 ${t}_vnfd.yaml
    while read -r key value
    do
      if [[ $key != \#* ]]; then
	  echo "s;$key;$value;g" >> sedtmpfile
      fi
    done < $ConfigFile
    sed -i "/\;\;g/d" sedtmpfile
    perl -p -i -e "s/\r//g" sedtmpfile
    sed -f sedtmpfile $2  > ${t}_vnfd.yaml
    /bin/rm -f sedtmpfile

    #read genFlag < <(cat $JSONFile | jq .[\"$t\"].vnf.genFlag | tr -d \")
    read genFlag < <(cat $JSONFile | jq .[\"$t\"].vnf.genFlag | tr -d \")
    if [ $genFlag == 'On' ]; then
  		echo "Converting for VNF element $t"
		#sed -i "s#myHostname#${hostnames_array[$t]}#g" ${t}_vnfd.yaml
  		read vnfid < <(cat $JSONFile | jq .[\"$t\"].vnf.vnfid | tr -d \")
  		read vnfName < <(cat $JSONFile | jq .[\"$t\"].vnf.vnfName | tr -d \")
  		read vnfShortName < <(cat $JSONFile | jq .[\"$t\"].vnf.vnfShortName | tr -d \")
  		read vnfDesc < <(cat $JSONFile | jq .[\"$t\"].vnf.vnfDesc | tr -d \")
  		read vduid < <(cat $JSONFile | jq .[\"$t\"].vnf.vduid | tr -d \")
  		read vduName < <(cat $JSONFile | jq .[\"$t\"].vnf.vduName | tr -d \")
  		read vduDesc < <(cat $JSONFile | jq .[\"$t\"].vnf.vduDesc | tr -d \")
		read myVNF < <(cat $JSONFile | jq .[\"$t\"].vnf.myVNF | tr -d \")
		if [[ $t == *fp_dp* ]]; then
			read vcpuCount < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_fp_vcpuCount' | tr -d \")
	                read memoryMb < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_fp_memoryMb' | tr -d \")
        	        read storageGb < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_fp_storageGb' | tr -d \")
  			read imageName < <(cat $JSONFile | jq .[\"$t\"].vnf.imagefpName | tr -d \")
		else
			read vcpuCount < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_vcpuCount' | tr -d \")
	                read memoryMb < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_memoryMb' | tr -d \")
	                read storageGb < <(cat $JSONFile | jq .[\"$t\"].vnf.vmFlavour.$myVNF'_storageGb' | tr -d \")
			read imageName < <(cat $JSONFile | jq .[\"$t\"].vnf.imageName | tr -d \")
		fi
  		read EPC_CONTEXT_NAME < <(cat $JSONFile | jq .[\"$t\"].vnf.EPC_CONTEXT_NAME | tr -d \")
  		read CONTROLLER_IP < <(cat $JSONFile | jq .[\"$t\"].vnf.CONTROLLER_IP | tr -d \")
  		read CONTROLLER_USER < <(cat $JSONFile | jq .[\"$t\"].vnf.CONTROLLER_USER | tr -d \")
  		read CONTROLLER_PASSWORD < <(cat $JSONFile | jq .[\"$t\"].vnf.CONTROLLER_PASSWORD | tr -d \")
		read EPC_NFV_BASE_SUB_PATH < <(cat $JSONFile | jq .[\"$t\"].vnf.EPC_NFV_BASE_SUB_PATH | tr -d \")
		read USER_ENV < <(cat $JSONFile | jq .[\"$t\"].vnf.USER_ENV | tr -d \")
                read HOME_ENV < <(cat $JSONFile | jq .[\"$t\"].vnf.HOME_ENV | tr -d \")
                #read sublen
                read PCRF_ADDRPAIR_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.PCRF_ADDRPAIR_CP | tr -d \")
		read PCRF_SUBLEN_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.PCRF_SUBLEN_CP | tr -d \")

                read MME_ADDRPAIR_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.MME_ADDRPAIR_CP | tr -d \")
		read MME_SUBLEN_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.MME_SUBLEN_CP | tr -d \")
                
                read SGW_ADDRPAIR_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.SGW_ADDRPAIR_CP | tr -d \")
		read SGW_SUBLEN_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.SGW_SUBLEN_CP | tr -d \")

                read PGW_ADDRPAIR_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.PGW_ADDRPAIR_CP | tr -d \")
		read PGW_SUBLEN_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.PGW_SUBLEN_CP | tr -d \")

                read TCE_ADDRPAIR_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.TCE_ADDRPAIR_CP | tr -d \")
		read TCE_SUBLEN_CP < <(cat $JSONFile | jq .[\"$t\"].vnf.TCE_SUBLEN_CP | tr -d \")

                read PGW_ADDRPAIR_DP < <(cat $JSONFile | jq .[\"$t\"].vnf.PGW_ADDRPAIR_DP | tr -d \")
		read PGW_SUBLEN_DP < <(cat $JSONFile | jq .[\"$t\"].vnf.PGW_SUBLEN_DP | tr -d \")

                read SGW_ADDRPAIR_DP < <(cat $JSONFile | jq .[\"$t\"].vnf.SGW_ADDRPAIR_DP | tr -d \")
		read SGW_SUBLEN_DP < <(cat $JSONFile | jq .[\"$t\"].vnf.SGW_SUBLEN_DP | tr -d \")
		if [[ $t == *dp* ]]; then
	        	#read ADDRPAIR < <(cat $JSONFile | jq .[\"$t\"].vnf.ADDRPAIR_DP | tr -d \")
			#read SUBLEN < <(cat $JSONFile | jq .[\"$t\"].vnf.SUBLEN_DP | tr -d \")
			read V6ADDRESS < <(cat $JSONFile | jq .$t.vnf.V6ADDRESS_DP | tr -d \")
                        read IPV6LEN < <(cat $JSONFile | jq .$t.vnf.SUBLENV6_DP | tr -d \")
		else
	        	#read ADDRPAIR < <(cat $JSONFile | jq .[\"$t\"].vnf.ADDRPAIR_CP | tr -d \")
			#read SUBLEN < <(cat $JSONFile | jq .[\"$t\"].vnf.SUBLEN_CP | tr -d \")
			read V6ADDRESS < <(cat $JSONFile | jq .$t.vnf.V6ADDRESS_CP | tr -d \")
                        read IPV6LEN < <(cat $JSONFile | jq .$t.vnf.SUBLENV6_CP | tr -d \")
		fi
  		sed -i "s/vnfid/$vnfid/g" ${t}_vnfd.yaml
  		sed -i "s/vnfName/$vnfName/g" ${t}_vnfd.yaml
  		sed -i "s/vnfShortName/$vnfShortName/g" ${t}_vnfd.yaml
  		sed -i "s/vnfDesc/$vnfDesc/g" ${t}_vnfd.yaml
  		sed -i "s/vduid/$vduid/g" ${t}_vnfd.yaml
  		sed -i "s/vduName/$vduName/g" ${t}_vnfd.yaml
  		sed -i "s/vduDesc/$vduDesc/g" ${t}_vnfd.yaml
  		sed -i "s/imageName/$imageName/g" ${t}_vnfd.yaml
		sed -i  "s/vx/$vcpuCount/g" ${t}_vnfd.yaml
  		sed -i "s/mx/$memoryMb/g" ${t}_vnfd.yaml
  		sed -i "s/sx/$storageGb/g" ${t}_vnfd.yaml
  		#sed -i "s/myHostname/$myHostname/g" ${t}_vnfd.yaml
  		sed -i "s/myVNF/$myVNF/g" ${t}_vnfd.yaml
		#sed -i "s/myHostname/${hostnames_array[$t]}/g" ${t}_vnfd.yaml
  		sed -i "s/myHostname/${new_HA[$t]}/g" ${t}_vnfd.yaml
		sed -i "s/CONTROLLER_IP/$CONTROLLER_IP/g" ${t}_vnfd.yaml
  		sed -i "s/CONTROLLER_USER/$CONTROLLER_USER/g" ${t}_vnfd.yaml
  		sed -i "s/CONTROLLER_PASSWORD/$CONTROLLER_PASSWORD/g" ${t}_vnfd.yaml
		sed -i "s#EPC_NFV_BASE_SUB_PATH#$EPC_NFV_BASE_SUB_PATH#g" ${t}_vnfd.yaml
		sed -i "s#EPC_CONTEXT_NAME#$EPC_CONTEXT_NAME#g" ${t}_vnfd.yaml
		sed -i "s#USER_ENV#$USER_ENV#g" ${t}_vnfd.yaml
                sed -i "s#HOME_ENV#$HOME_ENV#g" ${t}_vnfd.yaml
		#sed -i "s#ADDRPAIR#$ADDRPAIR#g" ${t}_vnfd.yaml
		#sed -i "s#SUBLEN#$SUBLEN#g" ${t}_vnfd.yaml

                #sed
                sed -i "s#PCRF_ADDRPAIR_CP#$PCRF_ADDRPAIR_CP#g" ${t}_vnfd.yaml
                sed -i "s#PCRF_SUBLEN_CP#$PCRF_SUBLEN_CP#g" ${t}_vnfd.yaml

                sed -i "s#MME_ADDRPAIR_CP#$MME_ADDRPAIR_CP#g" ${t}_vnfd.yaml
                sed -i "s#MME_SUBLEN_CP#$MME_SUBLEN_CP#g" ${t}_vnfd.yaml

                sed -i "s#SGW_ADDRPAIR_CP#$SGW_ADDRPAIR_CP#g" ${t}_vnfd.yaml
                sed -i "s#SGW_SUBLEN_CP#$SGW_SUBLEN_CP#g" ${t}_vnfd.yaml

                sed -i "s#PGW_ADDRPAIR_CP#$PGW_ADDRPAIR_CP#g" ${t}_vnfd.yaml
                sed -i "s#PGW_SUBLEN_CP#$PGW_SUBLEN_CP#g" ${t}_vnfd.yaml

                sed -i "s#TCE_ADDRPAIR_CP#$TCE_ADDRPAIR_CP#g" ${t}_vnfd.yaml
                sed -i "s#TCE_SUBLEN_CP#$TCE_SUBLEN_CP#g" ${t}_vnfd.yaml

                sed -i "s#PGW_ADDRPAIR_DP#$PGW_ADDRPAIR_DP#g" ${t}_vnfd.yaml
                sed -i "s#PGW_SUBLEN_DP#$PGW_SUBLEN_DP#g" ${t}_vnfd.yaml

                sed -i "s#SGW_ADDRPAIR_DP#$SGW_ADDRPAIR_DP#g" ${t}_vnfd.yaml
                sed -i "s#SGW_SUBLEN_DP#$SGW_SUBLEN_DP#g" ${t}_vnfd.yaml



		sed -i "s#V6ADDRESS#$V6ADDRESS#g" ${t}_vnfd.yaml
                sed -i "s#IPV6LEN#$IPV6LEN#g" ${t}_vnfd.yaml
		autohealid=$vduid'_'autoheal
                sed -i "s/autohealid/$autohealid/g" ${t}_vnfd.yaml
		#sed -e "s/\"cloudInit\"/$(<$userData/${t}.sh sed -e 's/[\&/]/\\&/g' -e 's/$/\\n/' | tr -d '\n')/g" -i ${t}_vnfd.yaml 
		mkdir $t'_vnf'; mv ${t}_vnfd.yaml $t'_vnf'
		tar -czvf $t'_vnf.tar.gz' $t'_vnf'
		# osm package-build $t'_vnf'
    fi
}

generate_ns_param(){
    echo -e "##  Generating the ${GREEN} OSM NSD${NC} Packages  ##\n"
    echo "file is $3"
    t=$(echo $3 | awk '{print $2}')
    for t in ${arr[@]}; do
        read genFlag < <(cat $JSONFile | jq .[\"$t\"].vnf.genFlag | tr -d \")
        if [[ $genFlag == 'On' ]]; then
		#if [[ $t == *dp* ]]; then
                #        read nwkName_dp < <(cat $JSONFile | jq .[\"$t\"].ns.nwkName_dp | tr -d \")
		#	sed -i "s/nwkName_dp/$nwkName_dp/g" $2;
                #else
                #        read nwkName_cp < <(cat $JSONFile | jq .[\"$t\"].ns.nwkName_cp | tr -d \")
		#	sed -i "s/nwkName_cp/$nwkName_cp/g" $2;
                #fi
		#echo $nwkName_cp $nwkName_dp
                MME_NETWORK_NAME=$(awk '/MME_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/MME_CP/$MME_NETWORK_NAME/g" $2;
                SGW_NETWORK_NAME=$(awk '/SGW_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/SGW_CP/$SGW_NETWORK_NAME/g" $2;
                PGW_NETWORK_NAME=$(awk '/PGW_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/PGW_CP/$PGW_NETWORK_NAME/g" $2;
                PCRF_NETWORK_NAME=$(awk '/PCRF_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/PCRF_CP/$PCRF_NETWORK_NAME/g" $2;
                TCE_NETWORK_NAME=$(awk '/TCE_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/TCE_NODE1/$TCE_NETWORK_NAME/g" $2;
                SGW_DP_NETWORK_NAME=$(awk '/SGW_DP_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/SGW_DP/$SGW_DP_NETWORK_NAME/g" $2;
                sed -i "s/SGW_FP/$SGW_DP_NETWORK_NAME/g" $2;
                PGW_DP_NETWORK_NAME=$(awk '/PGW_DP_NETWORK_NAME/{print $NF}' $ConfigFile)
                sed -i "s/PGW_DP/$PGW_DP_NETWORK_NAME/g" $2;
                sed -i "s/PGW_FP/$PGW_DP_NETWORK_NAME/g" $2;


                

		vnfip=$(cat $JSONFile | jq .[\"$t\"].ns | grep PHYSICAL_IPV4 | awk '{print $2}' | tr -d \" | tr -d \",)
		t1=${t}'_IP1'
		sed -i "s/$t1/$vnfip/g" $2;
		vnfip6=$(cat $JSONFile | jq .[\"$t\"].ns | grep PHYSICAL_IPV6 | awk '{print $2}' | tr -d \" | tr -d \",)
		t2=${t}'_V6IP1'
		sed -i "s/$t2/$vnfip6/g" $2;
        fi
    done
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
