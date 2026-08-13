#!/bin/bash

echo "**** Removing the Old tar files ****"
rm *.gz

echo "Please Enter the NSD Node Format (ns/nsd)"
read nsd_format

echo "Please Enter the VNFD Node Format (vnf/vnfd)"
read vnfd_format

ns_node_name=$(find *$nsd_format | head -n 1)
ns_node_yaml=$(find *$nsd_format | tail -n 1)

vnf_node_name=$(find *$vnfd_format | head -n 1)
vnf_node_yaml=$(find *$vnfd_format | tail -n 1)

echo "**** Please Enter the New NSD Name ****"
read new_nsd_name

echo ""

echo "**** Please Enter the New VNFD Name ****"
read new_vnfd_name

echo ""

old_nsd_name=$(grep -e nsd $ns_node_yaml | tail -n 1 | awk '{print$2}')
old_vnfd_name=$(grep -e vnfd $ns_node_yaml | tail -n 1 | awk '{print$2}')

echo "Renaming NSD Node with $new_nsd_name"

sed -i "s/$old_nsd_name/$new_nsd_name/g" $ns_node_yaml
sed -i "s/$old_vnfd_name/$new_vnfd_name/g" $ns_node_yaml

mv $ns_node_yaml $ns_node_name/$new_nsd_name.yaml
mv $ns_node_name $new_nsd_name

echo ""

echo "Renaming VNFD Node with $new_vnfd_name"

sed -i "s/$old_vnfd_name/$new_vnfd_name/g" $vnf_node_yaml

mv $vnf_node_yaml $vnf_node_name/$new_vnfd_name.yaml
mv $vnf_node_name $new_vnfd_name

echo ""
tar -cvzf $new_nsd_name.tar.gz $new_nsd_name
tar -cvzf $new_vnfd_name.tar.gz $new_vnfd_name

echo ""


echo "**** Nodes Rename Completed ****"
echo ""
echo "**** Please Verify before Uploading in TEOSM ****"
echo ""
echo "Please Enter the CFG File Name"
read cfg_name
echo ""

echo "****************** NSD Node Verification ******************"
echo ""

echo "NSD Node Name: $(grep -i nsd $new_nsd_name/$new_nsd_name.yaml | tail -n 1 | awk '{print$2}')"
echo "-----------"
echo "Verify the IP Address in CFG and Node"
echo "-------"

ip_node=$(grep -e ip-address $new_nsd_name/$new_nsd_name.yaml | awk '{print$2}')
ip_cfg=$(grep -e PHYSICAL_IPV4 $cfg_name | head -n 2)
echo "IP in NSD Node: 
$ip_node"
echo "----------"
echo "IP in CFG: 
$ip_cfg"

echo ""
echo "Verify Network in CFG and Node"
echo "-------------"

network_node=$(grep -e "vim-network-name" $new_nsd_name/$new_nsd_name.yaml | awk '{print$2}')
network_cfg=$(grep -e NETWORK $cfg_name)

echo "VIM-Network in NSD Node: 
$network_node"
echo ""
echo "--------------"
echo "VIM-Network in CFG: 
$network_cfg"
echo "-----------"


echo ""
echo "****************** VNFD Node Verification ******************"
echo ""
echo "VNFD Node Name: $(grep -e vnfd $new_nsd_name/$new_nsd_name.yaml | head -n 1 | awk '{print$2}')"
echo "------------------"
echo "Image in VNFD: 
$(grep -i IMAGE $new_vnfd_name/$new_vnfd_name.yaml | tail -n 1 | awk '{print$2}')"
echo "----------------"
echo "Image in CFG 
$(grep -i IMAGE $cfg_name)"

echo ""
echo "Controller Details in CFG"
echo "--------"
echo "Controller User: $(grep -i CONTROLLER_USER $cfg_name | awk '{print$2}')"
echo "Controller IP: $(grep -i CONTROLLER_IP $cfg_name | awk '{print$2}')"
echo "Controller Password: $(grep -i CONTROLLER_PASSWORD $cfg_name | awk '{print$2}')"
echo ""
echo "-----------"
echo "Context Name in CFG
$(grep -e CONTEXT_NAME $cfg_name)"
echo "--------"
echo ""
echo "Verify the Cloud-INIT"
echo "--------------------"
sed -n '/cloud-init/,/int-cpd/p' $new_vnfd_name/$new_vnfd_name.yaml
echo ""
echo "---------"
echo "Flavors in CFG 
$(grep -e flv $cfg_name | awk '{print$2}')"
echo ""
echo "--------------"
echo "Verify the Resources"
echo "------------------"
sed -n '/virtual-compute-desc/,/size-of-storage/p' $new_vnfd_name/$new_vnfd_name.yaml

echo ""

echo "Do you want to upload in the TEOSM(y/n)"
read node_upload

if [[ $node_upload == "y" ]];then
    echo "Please Enter the TEOSM Circle Details"
    echo "Please Enter the Username"
    read username
    echo ""
    echo "Please Enter the Password"
    read password
    echo ""
    echo "Please Enter the Project Name"
    read project

    export OSM_USER=$username
    export OSM_PASSWORD=$password
    export OSM_PROJECT=$project

    user_name=$(osm user-show $username | grep $username  | awk {'print$4'} | tr -d '",')
    if [[ $user_name == $username ]];then
	    echo "You have successfully Logged in $(osm user-show $username | grep project_name | awk {'print$4'} | tr -d '",') Circle"
        osm vnfd-create $new_vnfd_name.tar.gz
        osm nsd-create $new_nsd_name.tar.gz
    else 
	    echo "LogIn failed, Please retry"
	    exit 0
    fi
fi
echo "------------ The End -------------"
