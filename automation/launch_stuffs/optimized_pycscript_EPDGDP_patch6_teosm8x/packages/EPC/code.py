# Import variables
import variables

# Import common functions
import common
import template_formation
import nsconfig

# Import Packages
import json
import os
import subprocess
import re
import os.path
import configparser
import sys
import requests
import collections

ipv6=str(input("\n\nEnter YES if the deployment requires IPV6 Support or NO if deployment doesnt require IPV6 Support\n"))

#json_file = file_load(variables.config["Config_files"]["Json_config"],"json")
try:
    node_name = os.environ["nsd_name"]
    if (os.environ["num_sgw_dp"] != ""):
        sgw_nodes = int(os.environ["num_sgw_dp"])
    else:
        sgw_nodes = 0
    if (os.environ["num_pgw_dp"] != ""):
        pgw_nodes = int(os.environ["num_pgw_dp"])
    else:
        pgw_nodes = 0
    context = "_"+os.environ["CONTEXT"]
    if variables.config["Options"].getboolean("fpdp"):
        dp_name = "fp_dp"
        if re.search("sgw_dp_node",node_name) or re.search("pgw_dp_node",node_name):
            raise SystemExit("Give appropriate fpdp option before proceeding")
    else:
        dp_name = "dp"
        if re.search("sgw_fp_dp_node",node_name) or re.search("pgw_fp_dp_node",node_name):
            raise SystemExit("Give appropriate fpdp option before proceeding")
    print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
    print("No of SGW and PGW DP nodes are",sgw_nodes,pgw_nodes)
    if re.search("dp_node",node_name):
        if re.search("sgw", node_name) and (int(re.findall(r'\d+', node_name)[-1]) > sgw_nodes):
            raise SystemExit("SGW DP node number is greater than total Dp nodes in lte_epc.cfg")
        if re.search("pgw", node_name) and (int(re.findall(r'\d+', node_name)[-1]) > pgw_nodes):
            raise SystemExit("PGW DP node number is greater than total Dp nodes in lte_epc.cfg")
    print("Context name =",context)
except Exception as e:
    print("Exception occured = ",e,"\n Please enter the correct number of sgw/pgw nodes in the config file")

try:
    template_files = json.loads(variables.config["Openstack"]["Template_files"])
    if (sgw_nodes <= 0):
        template_files.pop("sgw_"+dp_name+"_nodeN")
    elif (sgw_nodes >= 1 ):
        for i in range(1,sgw_nodes+1):
            key_name = "sgw_"+dp_name+"_node"+str(i)
            if i == 1:
                template_files.update({key_name : template_files["sgw_"+dp_name+"_nodeN"]})
                template_files.pop("sgw_"+dp_name+"_nodeN")
            else:
                template_files.update({key_name : template_files["sgw_"+dp_name+"_node1"]})
                variables.json_file[key_name] = variables.json_file["sgw_"+dp_name+"_node1"]
                variables.json_file[key_name] = common.replace_deep(variables.json_file[key_name],"sgw_"+dp_name+"_node1",key_name)
                variables.json_file[key_name]["ns"]["SGW_NODE"+str(i+2)+"_PHYSICAL_IPV4"] = variables.json_file[key_name]["ns"].pop("SGW_NODE3_PHYSICAL_IPV4")
                variables.json_file[key_name]["ns"]["SGW_NODE"+str(i+2)+"_PHYSICAL_IPV6"] = variables.json_file[key_name]["ns"].pop("SGW_NODE3_PHYSICAL_IPV6")
                variables.json_file[key_name]["ns"] = collections.OrderedDict(variables.json_file[key_name]["ns"])
                variables.json_file[key_name]["ns"].move_to_end("nwkName_dp")
    if (pgw_nodes <= 0):
        template_files.pop("pgw_"+dp_name+"_nodeN")
    elif (pgw_nodes >= 1 ):
        for i in range(1,pgw_nodes+1):
            key_name = "pgw_"+dp_name+"_node"+str(i)
            if i == 1:
                template_files.update({key_name : template_files["pgw_"+dp_name+"_nodeN"]})
                template_files.pop("pgw_"+dp_name+"_nodeN")
            else:
                template_files.update({key_name : template_files["pgw_"+dp_name+"_node1"]})
                variables.json_file[key_name] = variables.json_file["pgw_"+dp_name+"_node1"]
                variables.json_file[key_name] = common.replace_deep(variables.json_file[key_name],"pgw_"+dp_name+"_node1",key_name)
                #echo "PGW_NODE"+str(i+2)+"_PHYSICAL_IPV4"
                variables.json_file[key_name]["ns"]["PGW_NODE"+str(i+2)+"_PHYSICAL_IPV4"] = variables.json_file[key_name]["ns"].pop("PGW_NODE3_PHYSICAL_IPV4")
                variables.json_file[key_name]["ns"]["PGW_NODE"+str(i+2)+"_PHYSICAL_IPV6"] = variables.json_file[key_name]["ns"].pop("PGW_NODE3_PHYSICAL_IPV6")
                variables.json_file[key_name]["ns"] = collections.OrderedDict(variables.json_file[key_name]["ns"])
                variables.json_file[key_name]["ns"].move_to_end("nwkName_dp")
    with open(variables.config["Config_files"]["Json_config"],"w") as f:
        json.dump(variables.json_file, f, indent=8, separators=(',', ': '))
except Exception as e:
    print("Exception occured = ",e)

try:
    node_name = os.environ["nsd_name"]
    for k,v in template_files.items():
        if k==node_name:
            template_files_new = {k:v}
    template_files = template_files_new
except Exception as e:
    print("Exception occured = ",e)

if variables.config["Options"].getboolean("fpdp"):
    pop_keys = []
    for i in range(0, len(list(template_files.keys()))):
        if re.search("dp",list(template_files.keys())[i]) and (re.search("fp_dp",list(template_files.keys())[i]) == None):
            pop_keys.append((list(template_files.keys())[i]))
    for i in pop_keys:
        if i in template_files:
            template_files.pop(i)
else:
    pop_keys = []
    for i in range(0, len(list(template_files.keys()))):
        if re.search("fp_dp",list(template_files.keys())[i]):
            pop_keys.append((list(template_files.keys())[i]))
    for i in pop_keys:
        if i in template_files:
            template_files.pop(i)

template_new = dict(template_files)
for i in range(0, len(list(template_files.keys()))):
    node = list(template_files.keys())[i]
    # key_name = node[:node.find("_")] + context + node[node.find("_") : ]
 
    context_name = os.environ["CONTEXT"]
    node_name_split = node.split("_")
    last_part = node_name_split[-1]
    node_name_split[-1] = context_name + "_" + last_part
    key_name = "_".join(node_name_split)

    template_new.update({key_name : template_files[node]})
    template_new.pop(node)
    variables.json_file[key_name] = variables.json_file[node]
    variables.json_file[key_name] = common.replace_deep(variables.json_file[key_name],node,key_name)
with open(variables.config["Config_files"]["Json_config"],"w") as f:
    json.dump(variables.json_file, f, indent=8, separators=(',', ': '))
template_files = dict(template_new)
# if (node_name.find("_") == -1):
#     node_name = node_name + context
# else:
#     node_name = node_name[:node_name.find("_")] + context + node_name[node_name.find("_"):]

node_name = node_name + "_" + context_name

def main():
     # Create VNFDs

    vnfd_template="osm_template/"+variables.config["Config_files"]["Vnfd_template"]
    subprocess.check_call(['cp', vnfd_template, '.'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    common.call_shell("PARAM")
    json_vnf_details = list(variables.json_file.values())[0]["vnf"]
    Controller_IP = json_vnf_details["CONTROLLER_IP"]
    Controller_Username = json_vnf_details["CONTROLLER_USER"]
    Controller_Password = json_vnf_details["CONTROLLER_PASSWORD"]
    for vnf_name,template in template_files.items():
        if not variables.config["Openstack"]["Tosca_template_path"].endswith('/'):
            template_file=variables.config["Openstack"]["Tosca_template_path"]+'/'+template
        else:
            template_file=variables.config["Openstack"]["Tosca_template_path"]+template
        if(variables.config["Openstack"].getboolean("Template_format_Sol006") == 0):
            old_template = variables.config["Config_files"]["old_Vnfd_template"]
            variables.config.set("Config_files","Vnfd_template",old_template)
            template_formation.vnftemplate(Controller_IP, Controller_Username, Controller_Password, template_file, vnf_name, ipv6)
        else:
            template_formation.vnftemplate_sol006(Controller_IP, Controller_Username, Controller_Password, template_file, vnf_name, ipv6)
        print("Creating VNFD for the node",vnf_name)
        vnfd="VNFD " + vnf_name
        common.call_shell(vnfd)
        variables.vnfd_packages.append(vnf_name+"_vnf.tar.gz")
    print("VNFD's are ready. \n",variables.vnfd_packages,"\n\n")

    # Create NSDs

    #common.call_shell("PARAM")
    if len(template_files) == 1:
        variables.nsd_nos["nsd"] = [list(template_files.keys())[0],]
    else:
        #for j in range (0, len(template_files.keys())):
            variables.nsd_nos["nsd"+str(1)] = list(template_files.keys())
            print(variables.nsd_nos.items())
            print(list(template_files.items()))
    #variables.nsd_nos = json.loads(variables.config["Openstack"]["NSD_Segregation"])
    dp, cp, dp_nodes,cp_nodes,vld_count=0, 0, [], [],0
    dp_nwkname = ""
    #with open(variables.config["Config_files"]["Config_file"], "r") as f:
        #data = f.readlines()
        #for line in data:
            #if re.search("NETWORK_NAME",line):
                #cp_nwkname = line.strip().split(" ")[1]
            #if re.search("NETWORK_DP_NAME",line):
                #dp_nwkname = line.strip().split(" ")[1]

    if (dp_nwkname != "") and (cp_nwkname != dp_nwkname):
        for i in range(0, len(list(template_files.keys()))):
            if re.search("dp",list(template_files.keys())[i]):
                dp=1
                dp_nodes.append(list(template_files.keys())[i])
            #elif re.search("cp",list(template_files.keys())[i]):
            else:
                cp=1
                cp_nodes.append(list(template_files.keys())[i])
    if (dp==1) and(cp==1):
        vld_count=2
        template_nodes_list = [cp_nodes,dp_nodes]
        print("cp and dp nodes div",template_nodes_list)
        nwkName = ["nwkName_cp","nwkName_dp"]
    else:
        vld_count=1
        template_nodes_list=[list(template_files.keys()),]
        if (dp==1):
            nwkName = ["nwkName_dp",]
        elif(cp==1):
            nwkName = ["nwkName_cp",]
        else:
            nwkName = ["nwkName_cp",]
    print(f'|||||||||||||||||||||||||||||||||||||{node_name}')
    for key,value in variables.nsd_nos.items():
        print("Creating NSD",key,value,"\n\n")
        nsd_template = variables.config["Config_files"]["Nsd_template"]
        if(variables.config["Openstack"].getboolean("Template_format_Sol006") == 0):
            old_template = variables.config["Config_files"]["old_Nsd_template"]
            variables.config.set("Config_files","Nsd_template",old_template)
            nsfile = template_formation.nstemplate(node_name, key, value, vld_count, template_nodes_list,nwkName,ipv6)
        else:
            nsfile = template_formation.nstemplate_sol006(node_name, key, value,vld_count, template_nodes_list,nwkName,ipv6)
        #variables.config.set("Config_files","Nsd_template",nsfile)
        #nsconfig.populate_json()
        variables.config.set("Config_files","Nsd_template",nsfile)
        for vnf in value:
            nsd = "NSD " + vnf
            common.call_shell(nsd)
        ns_dir = node_name+"_"+key
        common.nsdcreate(nsfile,ns_dir)
        variables.nsd_packages.append(ns_dir+".tar.gz")
        variables.config.set("Config_files","Nsd_template",nsd_template)
    print("NSD's are ready. \n",variables.nsd_packages,"\n\n")

    #Upload Packages
    if(variables.config["Options"].getint("option") == 2):
        # VNFD package upload
        vnfd_id_list = common.vnfd_upload(variables.vnfd_packages)

        # Upload NSD package
        nsd_id = common.nsd_upload(variables.nsd_packages)

        
    # Clean up Json after Packages Creation
    #for i in range(0, len(list(template_files.keys()))):
        #key_name = list(template_files.keys())[i]
         #variables.json_file.pop(key_name)
    #with open(variables.config["Config_files"]["Json_config"],"w") as f:
        #json.dump(variables.json_file, f, indent=8, separators=(',', ': '))
    
if __name__ == "__main__":
    main()
