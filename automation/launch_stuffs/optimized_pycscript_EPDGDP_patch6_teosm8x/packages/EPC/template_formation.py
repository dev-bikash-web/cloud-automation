import variables
import common
import code
import json
import ruamel.yaml
from ruamel.yaml.scalarstring import PreservedScalarString as pss
import subprocess
import paramiko
import copy
import re
import sys, os
yaml = ruamel.yaml.YAML()
yaml.allow_duplicate_keys = True

def vnftemplate(Ip, user, passwd, tosca_template, vnf_name, ipv6): # Fetching tosca template file and updating if required
        try:
            vnfd_template="osm_template/"+variables.config["Config_files"]["Vnfd_template"]
            subprocess.check_call(['cp', vnfd_template, '.'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            osm_template_data = common.file_load(variables.config["Config_files"]["Vnfd_template"])

            # Getting the template file from openstack
            print("Connecting to the server to fetch template file details\n")
            host,port = Ip,22
            transport = paramiko.Transport((host,port))
            username,password = user,passwd
            transport.connect(None,username,password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("....Connected successfully\n")
            with sftp.open(tosca_template, "r") as f:
                data = yaml.load(f)
            # for ind, elem in enumerate(data["vnfd-catalog"]["vnfd"]): # Can be used in case of multiple vdu having different userdata
            #    for ind1, elem1 in enumerate(elem["vdu"]):
            tosca_userdata = data["topology_template"]["node_templates"]["VDU1"]["properties"]["user_data"].split("\n")

            # Allowed Address Pair
            print(f'@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@{vnf_name}')
            if "allowed_address_pairs" in data["topology_template"]["node_templates"]["CP1"]["properties"] and variables.config["cloud_init"].getboolean("AllowedAddressPair"):
                if ipv6 == "NO":
                    cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=ADDRPAIR/SUBLEN"\n'
                else:
                    cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=ADDRPAIR/SUBLEN"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
            else:
                cloud_init='echo "Not setting Allowed Address Pair"\n'
            cloud_init = pss(cloud_init)
            
            #Checking if "/bin/bash" present in cloud init
            if "#!/bin/bash" in tosca_userdata:
                value = tosca_userdata.index("#!/bin/bash")
            elif "#!/bin/sh" in tosca_userdata:
                value = tosca_userdata.index("#!/bin/sh")
            else:
                tosca_userdata.insert(0, "#!/bin/bash")
                value = 0

            # Hostname setting
            if variables.config["cloud_init"].getboolean("Hostname"):
                cloud_init = pss("hostname myHostname \nsed -i 's/.*/myHostname/g' /etc/hostname\n" + str(cloud_init))
            tosca_userdata.insert(value+1, cloud_init)
            osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["cloud-init"]="\n".join(tosca_userdata)

            # Feature suuport
            if(variables.config["Vnfd_specifications"].getboolean("monitoring_support") == 0):
                if "monitoring-param" in osm_template_data["vnfd-catalog"]["vnfd"][0]:
                    osm_template_data["vnfd-catalog"]["vnfd"][0].pop("monitoring-param")
                if "monitoring-param" in osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]:
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0].pop("monitoring-param")
            if(variables.config["Vnfd_specifications"].getboolean("heal_support") == 0):
                if "heal" in osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]:
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0].pop("heal")
            if(variables.config["Vnfd_specifications"].getboolean("notification_support") == 0):
                if "alarm" in osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]:
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0].pop("alarm")

            heal_params = variables.config["Vnfd_specifications"]["heal"]
            notification_api = variables.config["Vnfd_specifications"]["CNOPS_IP"]
            if "heal" in osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]:
                osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["heal"]["heal-type"] = heal_params
            if "alarm" in osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]:
                for i in range(0,len(osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["alarm"])):
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["alarm"][i]["actions"]["alarm"][0]["url"] = notification_api
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["alarm"][i]["actions"]["ok"][0]["url"] = notification_api
                    osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["alarm"][i]["actions"]["insufficient-data"][0]["url"] = notification_api
            
            #Connection points based on VLDs
            cap = [value for key,value in data["node_types"].items() if "tosca.nodes.nfv" in key]
            variables.ns_template_structure[vnf_name] = len(cap[0]["capabilities"])
            osm_template_data["vnfd-catalog"]["vnfd"][0]["connection-point"] = []
            osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["interface"] = []
            for i in range(0,len(cap[0]["capabilities"])):
                osm_template_data["vnfd-catalog"]["vnfd"][0]["connection-point"].append({"id" : "mgnt"+str(i+1),"name" : "mgnt"+str(i+1), "short-name" : "mgnt"+str(i+1)})
                osm_template_data["vnfd-catalog"]["vnfd"][0]["vdu"][0]["interface"].append({"name" : "eth"+str(i),"type" : "EXTERNAL", "virtual-interface" : {"type":"PARAVIRT"},"external-connection-point-ref" : "mgnt"+str(i+1)})
            

            with open(variables.config["Config_files"]["Vnfd_template"],'w') as fp:
                yaml.dump(osm_template_data, fp)
            print("Template file changed for",vnf_name)

        except Exception as e:
            raise SystemExit('Error occured while template change',e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

def nstemplate(node_name, key, value, vld_count, template_nodes_list, nwkName, ipv6):
    try:
        print("Preparing template file in old format",variables.config["Config_files"]["Nsd_template"])
        nsd_template_data = common.file_load(variables.config["Config_files"]["Nsd_template"])
        nsd_template_data["nsd-catalog"]["nsd"][0]["id"] = node_name+"_"+key
        nsd_template_data["nsd-catalog"]["nsd"][0]["name"] = node_name+"_"+key
        nsd_template_data["nsd-catalog"]["nsd"][0]["short-name"] = node_name+"_"+key
        nsd_template_data["nsd-catalog"]["nsd"][0]["description"] = node_name+"_"+key+" Network Service"
        constituent_vnfd = []
        vld_list = []
        
        #Add VLDs 
        #vld_no = max([variables.ns_template_structure[i] for i in value if i in variables.ns_template_structure.keys()])
        nsd_template_data["nsd-catalog"]["nsd"][0]["vld"] = []
        for i in range(0,vld_count):
            vld_list.append([])
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"].append({})
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["id"] = node_name+"_"+key+"_vld"+str(i)
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["name"] = "mgmt"+str(i+1)
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["short-name"] = "mgmt"+str(i+1)
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["type"] = "ELAN"
            if i==0:
                nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["mgmt-network"] = "true"
            #nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["vim-network-name"] = "nwkName"+str(i+1)
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["vim-network-name"] = nwkName[i]
            for j in range(0,len(template_nodes_list[i])):
                vnfd_dicts = {"member-vnf-index-ref":str(list(code.template_files.keys()).index(template_nodes_list[i][j])+1)}
                vnfd_dicts["vnfd-connection-point-ref"] = "mgnt"+str(1)
                if ipv6 == "YES":
                    vnfd_dicts["ip-address"] = [template_nodes_list[i][j]+"_IP"+str(1), template_nodes_list[i][j]+"_V6IP"+str(1)]
                else:
                    vnfd_dicts["ip-address"] = template_nodes_list[i][j]+"_IP"+str(1)
                myvnfdcopy = vnfd_dicts.copy()
                vld_list[i].append(myvnfdcopy)

        for i in range(0,len(value)):
            dicts = {"member-vnf-index":str(i+1),"vnfd-id-ref": str(value[i]+"_vnfd")}
            constituent_vnfd.append(dicts)
        nsd_template_data["nsd-catalog"]["nsd"][0]["constituent-vnfd"] = constituent_vnfd
        for i in range(0,vld_count):
            nsd_template_data["nsd-catalog"]["nsd"][0]["vld"][i]["vnfd-connection-point-ref"] = copy.deepcopy(vld_list[i])
        
        nsfile = node_name+"_"+key+".yaml"
        with open(nsfile, 'w') as fp:
            yaml.dump(nsd_template_data, fp)
        return nsfile
    
    except Exception as e:
        raise SystemExit('Error occured =',e)

def vnftemplate_sol006(Ip, user, passwd, tosca_template, vnf_name, ipv6):
        try:
            vnfd_template="osm_template/"+variables.config["Config_files"]["Vnfd_template"]
            subprocess.check_call(['cp', vnfd_template, '.'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            osm_template_data = common.file_load(variables.config["Config_files"]["Vnfd_template"])

            # Getting the template file from openstack
            print("Connecting to the server to fetch template file details\n")
            host,port = Ip,22
            transport = paramiko.Transport((host,port))
            username,password = user,passwd
            transport.connect(None,username,password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("....Connected successfully\n")
            with sftp.open(tosca_template, "r") as f:
                data = yaml.load(f)
            # for ind, elem in enumerate(data["vnfd-catalog"]["vnfd"]): # Can be used in case of multiple vdu having different userdata
            #    for ind1, elem1 in enumerate(elem["vdu"]):
            vnf = (vnf_name.split('_')[0] + '_' + vnf_name.split('_')[1]).upper()
            print(f'@@@@@@@@@@@@@@@@@@@@@@@@@@@{vnf}')

            tosca_userdata = data["topology_template"]["node_templates"]["VDU1"]["properties"]["user_data"].split("\n")

            # Allowed Address Pair
            if "allowed_address_pairs" in data["topology_template"]["node_templates"]["CP1"]["properties"] and variables.config["cloud_init"].getboolean("AllowedAddressPair"):
                if vnf == 'PCRF_CP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PCRF_ADDRPAIR_CP/PCRF_SUBLEN_CP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PCRF_ADDRPAIR_CP/PCRF_SUBLEN_CP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
            #if "allowed_address_pairs" in data["topology_template"]["node_templates"]["CP1"]["properties"] and variables.config["cloud_init"].getboolean("AllowedAddressPair"):
                if vnf == 'MME_CP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=MME_ADDRPAIR_CP/MME_SUBLEN_CP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=MME_ADDRPAIR_CP/MME_SUBLEN_CP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'SGW_CP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_CP/SGW_SUBLEN_CP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_CP/SGW_SUBLEN_CP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'PGW_CP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_CP/PGW_SUBLEN_CP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_CP/SUBLEN_CP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'TCE_CDOT':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=TCE_ADDRPAIR_CP/TCE_SUBLEN_CP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=TCE_ADDRPAIR_CP/TCE_SUBLEN_CP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'SGW_DP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_DP/SGW_SUBLEN_DP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_DP/SGW_SUBLEN_DP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'PGW_DP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_DP/PGW_SUBLEN_DP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_DP/PGW_SUBLEN_DP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'PGW_FP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_DP/PGW_SUBLEN_DP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=PGW_ADDRPAIR_DP/PGW_SUBLEN_DP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
                if vnf == 'SGW_FP':
                    if ipv6 == "NO":
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_DP/SGW_SUBLEN_DP"\n'
                    else:
                        cloud_init='echo "Setting Allowed Address Pair"\nmyport=$(sshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port list --fixed-ip ip-address=$(hostname -I | awk \'{print $1}\')" | awk \'{print $2}\' | tail -2 | head -1)\necho $myport\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=SGW_ADDRPAIR_DP/SGW_SUBLEN_DP"\nsshpass -pCONTROLLER_PASSWORD ssh -o StrictHostKeyChecking=no CONTROLLER_USER@CONTROLLER_IP ". USER_ENV; openstack port set $myport --allowed-address ip-address=V6ADDRESS/IPV6LEN"\n'
            else:
                cloud_init='echo "Not setting Allowed Address Pair"\n'
            
            cloud_init = pss(cloud_init)

            #Checking if "/bin/bash" present in cloud init
            if "#!/bin/bash" in tosca_userdata:
                value = tosca_userdata.index("#!/bin/bash")
            elif "#!/bin/sh" in tosca_userdata:
                value = tosca_userdata.index("#!/bin/sh")
            else:
                tosca_userdata.insert(0, "#!/bin/bash")
                value = 0

            # Hostname setting
            if variables.config["cloud_init"].getboolean("Hostname"):
                cloud_init = pss("hostnamectl set-hostname myHostname \nsed -i 's/.*/myHostname/g' /etc/hostname\n" + str(cloud_init))
            tosca_userdata.insert(value+1, cloud_init)
            osm_template_data["vnfd"]["vdu"][0]["cloud-init"]="\n".join(tosca_userdata)
            print("Writing the cloud init data into template file \n")

            # Feature suuport
            if(variables.config["Vnfd_specifications"].getboolean("monitoring_support") == 0):
                if "monitoring-parameter" in osm_template_data["vnfd"]["vdu"][0]:
                    osm_template_data["vnfd"]["vdu"][0].pop("monitoring-parameter")
            if(variables.config["Vnfd_specifications"].getboolean("notification_support") == 0):
                if "alarm" in osm_template_data["vnfd"]["vdu"][0]:
                    osm_template_data["vnfd"]["vdu"][0].pop("alarm")
            if ("insufficient-data") in osm_template_data["vnfd"]["vdu"][0]["alarm"][0]["actions"]:
                osm_template_data["vnfd"]["vdu"][0]["alarm"][0]["actions"].pop("insufficient-data")

            heal_params = variables.config["Vnfd_specifications"]["heal"]
            notification_api = variables.config["Vnfd_specifications"]["CNOPS_IP"]
            if "alarm" in osm_template_data["vnfd"]["vdu"][0]:
                for i in range(0,len(osm_template_data["vnfd"]["vdu"][0]["alarm"])):
                    osm_template_data["vnfd"]["vdu"][0]["alarm"][i]["actions"]["alarm"][0]["url"] = notification_api
                    osm_template_data["vnfd"]["vdu"][0]["alarm"][i]["actions"]["ok"][0]["url"] = notification_api
                    #osm_template_data["vnfd"]["vdu"][0]["alarm"][i]["actions"]["insufficient-data"][0]["url"] = notification_api

            #Connection points based on VLDs
            cap = [value for key,value in data["node_types"].items() if "tosca.nodes.nfv" in key]
            variables.ns_template_structure[vnf_name] = len(cap[0]["capabilities"])
            osm_template_data["vnfd"]["ext-cpd"] = []
            osm_template_data["vnfd"]["vdu"][0]["int-cpd"] = []
            for i in range(0,len(cap[0]["capabilities"])):
                osm_template_data["vnfd"]["ext-cpd"].append({"id" : "mgnt"+str(i+1)+"-ext","int-cpd" : {"cpd" : "int"+str(i+1),"vdu-id" : "vduid"}})
                osm_template_data["vnfd"]["vdu"][0]["int-cpd"].append({"id" : "int"+str(i+1), "virtual-network-interface-requirement" : [{"name" : "eth"+str(i), "position" : i+1, "virtual-interface" : {"type":"PARAVIRT"}}]})

            with open(variables.config["Config_files"]["Vnfd_template"],'w') as fp:
                yaml.dump(osm_template_data, fp)
            print("Template file changed for",tosca_template)

        except Exception as e:
            raise SystemExit('Error occured while template change',e)


def nstemplate_sol006(node_name, key, value, vld_count, template_nodes_list, nwkName, ipv6):
    try:
        print("Preparing NSD Template in SOl006 format",variables.config["Config_files"]["Nsd_template"])
        nsd_template_data = common.file_load(variables.config["Config_files"]["Nsd_template"])
        nsd_template_data["nsd"]["nsd"][0]["id"] = node_name+"_"+key
        nsd_template_data["nsd"]["nsd"][0]["name"] = node_name+"_"+key
        nsd_template_data["nsd"]["nsd"][0]["description"] = node_name+"_"+key+" Network Service"
        nsd_template_data["nsd"]["nsd"][0]["df"][0]["vnf-profile"] = []

        #Add VLDs
        #vld_no = max([variables.ns_template_structure[i] for i in value if i in variables.ns_template_structure.keys()])
        print(f'----------------------------------------------{node_name}')
        nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"] = []
        nsd_template_data["nsd"]["nsd"][0]["vnfd-id"] = []
        for i in range(0,vld_count):
            nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"].append({})
            
            if len(re.findall("dp",value[i])) > 0 or len(re.findall("fp_dp",value[i])) > 0:
                nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"][i]["id"] = "mgmt"+str(i+2)
            else:
                nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"][i]["id"] = "mgmt"+str(i+1)

            nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"][i]["mgmt-network"] = "true"
            nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"][i]["vim-network-name"] = (node_name.split('_')[0] + '_'+ node_name.split('_')[1]).upper()
            #nsd_template_data["nsd"]["nsd"][0]["virtual-link-desc"][i]["vim-network-name"] = "nwkName"+str(i+1)               
        for i in range(0,len(value)):
            nsd_template_data["nsd"]["nsd"][0]["vnfd-id"].append(str(value[i]+"_vnfd"))
            vnfd_dicts = {"id" : str(i+1),"vnfd-id":str(value[i]+"_vnfd")}
            vnfd_dicts["virtual-link-connectivity"] = [] #member-vnf-index-ref": str(i+1)} #, "ip-address": str(value[i]+"_vnfd")}
            for j in range(0,variables.ns_template_structure[value[i]]):
                #vnfd_dicts["virtual-link-connectivity"].append({"constituent-cpd-id":[{"constituent-base-element-id":str(i+1), "constituent-cpd-id" :"mgnt"+str(j+1)+"-ext","ip-address" :str(value[i]+"_IP"+str(j+1))},], "virtual-link-profile-id" :"mgmt"+str(j+1)})        
                if ipv6 == "YES":
                    if len(re.findall("dp",value[i])) > 0 or len(re.findall("fp_dp",value[i])) > 0:
                        vnfd_dicts["virtual-link-connectivity"].append({"constituent-cpd-id":[{"constituent-base-element-id":str(i+1), "constituent-cpd-id" :"mgnt"+str(j+1)+"-ext","ip-address" :[str(value[i]+"_IP"+str(j+1)), str(value[i]+"_V6IP"+str(j+1))]},], "virtual-link-profile-id" :"mgmt"+str(j+2)})
                    else:
                        vnfd_dicts["virtual-link-connectivity"].append({"constituent-cpd-id":[{"constituent-base-element-id":str(i+1), "constituent-cpd-id" :"mgnt"+str(j+1)+"-ext","ip-address" :[str(value[i]+"_IP"+str(j+1)), str(value[i]+"_V6IP"+str(j+1))]},], "virtual-link-profile-id" :"mgmt"+str(j+1)})
                else:
                    if len(re.findall("dp",value[i])) > 0 or len(re.findall("fp_dp",value[i])) > 0:
                        vnfd_dicts["virtual-link-connectivity"].append({"constituent-cpd-id":[{"constituent-base-element-id":str(i+1), "constituent-cpd-id" :"mgnt"+str(j+1)+"-ext","ip-address" :str(value[i]+"_IP"+str(j+1))},], "virtual-link-profile-id" :"mgmt"+str(j+2)})
                    else:
                        vnfd_dicts["virtual-link-connectivity"].append({"constituent-cpd-id":[{"constituent-base-element-id":str(i+1), "constituent-cpd-id" :"mgnt"+str(j+1)+"-ext","ip-address" :str(value[i]+"_IP"+str(j+1))},], "virtual-link-profile-id" :"mgmt"+str(j+1)})

            nsd_template_data["nsd"]["nsd"][0]["df"][0]["vnf-profile"].append(vnfd_dicts)

        nsfile = node_name+"_"+key+".yaml"
        with open(nsfile, 'w') as fp:
            yaml.dump(nsd_template_data, fp)
        return nsfile

    except Exception as e:
        raise SystemExit('Error occured =',e)