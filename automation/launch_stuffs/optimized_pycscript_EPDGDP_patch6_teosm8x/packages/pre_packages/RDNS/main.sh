#!/bin/bash
ConfigFile=$1
NS=rdns
JSONFile=$4
FLAVOR=$5

#List of Control Plane and Data Plane Nodes
declare -A ips=( [rdns_node1_IP1]="_NODE_1_IP" [rdns_node2_IP1]="_NODE_2_IP")
declare -A ip6s=( [rdns_node1_V6IP1]="_NODE_1_V6IP" [rdns_node2_V6IP1]="_NODE_2_V6IP")
declare -A netname=( [nwkName1]="_NETWORK_NAME" [nwkName2]="_NETWORK_NAME")

# Get the list of VNFs for which the yaml has to be generated
mapfile -t arr < <(cat $JSONFile | jq -r 'keys' | tr -d \" | tr -d \, | tr -d \ | tr -d \[ | tr -d \])

populate_json() {
    echo -e "##  Populating the ${GREEN}$JSONFile${NC} file from input cfg  ##\n"
    # Common Parameters getting from config file
    Image_name=$(awk -F'[=]' '/_IMAGE_NAME/{print $NF}' $ConfigFile)
    #echo $Image_name
    Controller_User=$(awk -F'[=]' '/_SYSTEM_CONTROLLER_USER/{print $NF}' $ConfigFile)
    #echo $Controller_User
    CONTROLLER_IP=$(awk -F'[=]' '/_SYSTEM_CONTROLLER_IP/{print $NF}' $ConfigFile)
    #echo $CONTROLLER_IP
    CONTROLLER_PASSWORD=$(awk -F'[=]' '/_SYSTEM_CONTROLLER_PASSWORD/{print $NF}' $ConfigFile)
    #echo $CONTROLLER_PASSWORD
    HNAME=$(awk -F'[=]' '/_NODE_NAME/{print $NF}' $ConfigFile)
    #echo $HNAME
    REL_PATH=$(awk -F'[=]' '/_RELEASE_FILE_PATH/{print $NF}' $ConfigFile)
    #echo $REL_PATH
    REL_FILE=$(awk -F'[=]' '/_RELEASE_NUM/{print $NF}' $ConfigFile)
    #echo $REL_FILE
    PROVIDER_NAME=$(awk -F'[=]' '/_NETWORK_NAME/{print $NF}' $ConfigFile)
    #echo $PROVIDER_NAME
    ADDRPAIR=$(awk -F'[=]' '/_SUBNET/{print $NF}' $ConfigFile)
    

    #Nodes Flavor getting from config file
    RDNS_vcpu_count=$(awk '/RDNS_VCPUCOUNT/{print $NF}' $FLAVOR)
    RDNS_memorymb=$(awk '/RDNS_MEMORYGB/{print $NF}' $FLAVOR)
    RDNS_storagegb=$(awk '/RDNS_STORAGEGB/{print $NF}' $FLAVOR)


    # Common Parameters populating into the JSON file
    sed -i 's/RDNS_NODE_NAME/'$HNAME'/g' $JSONFile
    sed -i '/CONTROLLER_IP/c\ \                      "CONTROLLER_IP\" : \"'$CONTROLLER_IP'\",' $JSONFile
    sed -i '/CONTROLLER_USER/c\ \                    "CONTROLLER_USER\" : \"'$Controller_User'\",' $JSONFile
    sed -i '/CONTROLLER_PASSWORD/c\ \                "CONTROLLER_PASSWORD\" : \"'$CONTROLLER_PASSWORD'\",' $JSONFile
    sed -i '/myHostname/c\ \                "myHostname\" : \"'$HNAME'\",' $JSONFile
    sed -i '/imageName/c\ \                      "imageName\" : \"'$Image_name'\",' $JSONFile
    sed -i '/nwkName/c\ \                       "nwkName\" : \"'$PROVIDER_NAME'\"' $JSONFile
    sed -i '/Rel_Path/c\ \                       "Rel_Path\" : \"'$REL_PATH'\",' $JSONFile
    sed -i '/Rel_File/c\ \                       "Rel_File\" : \"'$REL_FILE'\",' $JSONFile
    sed -i '/ADDRPAIR/c\ \                       "ADDRPAIR\" : \"'$ADDRPAIR'\",' $JSONFile
    sed -i '/USER_ENV/c\ \                       "USER_ENV\" : \"'/home/$Controller_User/admin-openrc'\",' $JSONFile
    sed -i '/HOME_ENV/c\ \                       "HOME_ENV\" : \"'/home/ubuntu/admin-openrc'\",' $JSONFile
    #Nodes Flavor populating into the JSON file
    sed -i '/vcpuCount/c\ \                          "vcpuCount\" : \"'$RDNS_vcpu_count'\",' $JSONFile
    sed -i '/memoryMb/c\ \                          "memoryMb\" : \"'$RDNS_memorymb'\",' $JSONFile
    sed -i '/storageGb/c\ \                          "storageGb\" : \"'$RDNS_storagegb'\"' $JSONFile

    # VNF Ip address (Unique Parameters) getting from config file and populating into the JSON File
    #for nodeip in ${myarr[@]}; do
        #myip=$(grep -r $nodeip $ConfigFile | awk -F'[=]' '{print $2}' |head -1)
        #sed -i '/'$nodeip'/c\ \                       "'$nodeip'\" : \"'$myip'\",' $JSONFile
        #perl -p -i -e "s/\r//g" $JSONFile
    #done

    perl -p -i -e "s/\r//g" $JSONFile
}
generate_vnfds(){
    	echo -e "##  Generating the ${GREEN} OSM VNFD${NC} Packages  ##\n"
    	# Replacing the values in userdata first
	t=$(echo $3 | awk '{print $2}')
	cp $2 ${t}_vnfd.yaml
	sed "s/=/ /g" $ConfigFile >sed_temp.txt
	while read -r key value
	do
	  if [[ $key != \#* ]]; then
                echo "s;$key;$value;g" >> sedtmpfile
          fi
	  #echo "s;$key;$value;g" >> sedtmpfile
	done < sed_temp.txt
	/bin/rm -f sed_temp.txt
	sed -i "/\;\;g/d" sedtmpfile
    	sed -f sedtmpfile $2  > ${t}_vnfd.yaml
	/bin/rm -f sedtmpfile	
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
                read memoryMb < <(cat $JSONFile | jq .$t.vnf.vmFlavour.memoryMb | tr -d \")
                read storageGb < <(cat $JSONFile | jq .$t.vnf.vmFlavour.storageGb | tr -d \")
                read myHostname < <(cat $JSONFile | jq .$t.vnf.myHostname | tr -d \")
		read NODE_ID < <(cat $JSONFile | jq .$t.vnf.NODE_ID | tr -d \")
                read CONTROLLER_IP < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_IP | tr -d \")
                read CONTROLLER_USER < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_USER | tr -d \")
                read CONTROLLER_PASSWORD < <(cat $JSONFile | jq .$t.vnf.CONTROLLER_PASSWORD | tr -d \")
		#read ADDRPAIR < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \")
		read ADDRPAIR < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \" | awk -F"/"  '{print $1}')
		read SUBLEN < <(cat $JSONFile | jq .$t.vnf.ADDRPAIR | tr -d \" | awk -F"/"  '{print $2}')
		read USER_ENV < <(cat $JSONFile | jq .$t.vnf.USER_ENV | tr -d \")
                read HOME_ENV < <(cat $JSONFile | jq .$t.vnf.HOME_ENV | tr -d \")
		read Rel_File < <(cat $JSONFile | jq .$t.vnf.Rel_File | tr -d \")
		read Rel_Path < <(cat $JSONFile | jq .$t.vnf.Rel_Path | tr -d \")
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
                sed -i "s/myHostname/$myHostname$NODE_ID/g" ${t}_vnfd.yaml
		sed -i "s/NODE_ID/$NODE_ID/g" ${t}_vnfd.yaml
                sed -i "s/myVNF/$myVNF/g" ${t}_vnfd.yaml
                sed -i "s/_SYSTEM_CONTROLLER_IP/$CONTROLLER_IP/g" ${t}_vnfd.yaml
                sed -i "s/_SYSTEM_CONTROLLER_USER/$CONTROLLER_USER/g" ${t}_vnfd.yaml
                sed -i "s/_SYSTEM_CONTROLLER_PASSWORD/$CONTROLLER_PASSWORD/g" ${t}_vnfd.yaml
		sed -i "s/CONTROLLER_IP/$CONTROLLER_IP/g" ${t}_vnfd.yaml
                sed -i "s/CONTROLLER_USER/$CONTROLLER_USER/g" ${t}_vnfd.yaml
                sed -i "s/CONTROLLER_PASSWORD/$CONTROLLER_PASSWORD/g" ${t}_vnfd.yaml

		sed -i "s#ADDRPAIR#$ADDRPAIR#g" ${t}_vnfd.yaml
		sed -i "s/REL_FILE/$Rel_File/g" ${t}_vnfd.yaml
		sed -i "s#_RDNS_RELEASE_FILE_PATH#$Rel_Path#g" ${t}_vnfd.yaml
		sed -i "s#REL_PATH#$Rel_Path#g" ${t}_vnfd.yaml
		sed -i "s#USER_ENV#$USER_ENV#g" ${t}_vnfd.yaml
                sed -i "s#HOME_ENV#$HOME_ENV#g" ${t}_vnfd.yaml
		sed -i "s#SUBLEN#$SUBLEN#g" ${t}_vnfd.yaml
                #sed -e "s/\"cloudInit\"/$(<$userData/${t}.sh sed -e 's/[\&/]/\\&/g' -e 's/$/\\n/' | tr -d '\n')/g" -i ${t}_vnfd.yaml
		autohealid=$vduid'_'autoheal
                sed -i "s/autohealid/$autohealid/g" ${t}_vnfd.yaml
                mkdir $t'_vnf'; mv ${t}_vnfd.yaml $t'_vnf'
                tar -czvf $t'_vnf.tar.gz' $t'_vnf'
		# osm package-build $t'_vnf'

        fi
    #done
}

generate_ns_param(){
    echo -e "##  Generating the ${GREEN} OSM NSD${NC} Packages  ##\n"  ##\n"
    t=$(echo $3 | awk '{print $2}')
    echo $t
    for key in ${!ips[@]}; do
        read myip < <(cat $JSONFile | jq .$t.ns.$key | tr -d \")
        #echo $myip
        #sed -i "s/$key/$myip/g" $2;
        #if [[ ! -z "$myip" ]] && echo "Not empty" || echo "Empty" ; then
        if [[ $myip != "null" ]]; then
                #echo $key $myip
                sed -i "s/$key/$myip/g" $2;
        fi
    done

    for key in ${!ip6s[@]}; do
        read myip < <(cat $JSONFile | jq .$t.ns.$key | tr -d \")
        #echo $myip
        #sed -i "s/$key/$myip/g" $2;
        #if [[ ! -z "$myip" ]] && echo "Not empty" || echo "Empty" ; then
        if [[ $myip != "null" ]]; then
                #echo $key $myip
                sed -i "s/$key/$myip/g" $2;
        fi
    done

    for key in ${!netname[@]}; do
        read mynwk < <(cat $JSONFile | jq .$t.ns.$key | tr -d \")
        #echo $mynwk
        if [[ $mynwk != "null" ]]; then
                #echo $key $mynwk
                sed -i "s/$key/$mynwk/g" $2;
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
