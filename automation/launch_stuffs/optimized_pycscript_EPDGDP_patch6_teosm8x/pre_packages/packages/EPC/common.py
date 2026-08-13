import variables
import json
import requests
import ruamel.yaml
import subprocess
import paramiko
import os
from ruamel.yaml.scalarstring import PreservedScalarString as pss

yaml = ruamel.yaml.YAML()
yaml.allow_duplicate_keys = True
requests.packages.urllib3.disable_warnings()

def file_load(file_name, package_type=None):
    with open(file_name, 'r') as fp:
        if (package_type == "json"):
            return json.load(fp)
        else:
            return yaml.load(fp)

def replace_deep(data, a, b):
    if isinstance(data, str):
        return data.replace(a, b)
    elif isinstance(data, dict):
        return {k: replace_deep(v, a, b) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_deep(v, a, b) for v in data]
    else:
        return data


def auth_token(): # Get Auth Token
    url = "https://"+variables.config["OSM"]["OSM_IP"]+"/osm/admin/v1/tokens"
    username = variables.config["OSM"]["OSM_Username"]
    password = variables.config["OSM"]["OSM_Password"]
    project = variables.config["OSM"]["OSM_Project"]
    r = requests.post(url, headers = {"Accept":"application/json"}, data = {"username":username,"password":password,"project":project}, verify=False)
    if(r.status_code != 200 and r.status_code != 201):
        raise Exception(r.json()["detail"])
    token = r.json()["id"]
    print("Fetched the authorization token")
    return token

def package_upload(package, token, package_type=None): # Upload VNFD and NSD Packages
    if (package_type == "nsd"):
        url = "https://"+variables.config["OSM"]["OSM_IP"]+"/osm/nsd/v1/ns_descriptors_content/"
    else:
        url = "https://"+variables.config["OSM"]["OSM_IP"]+"/osm/vnfpkgm/v1/vnf_packages_content/"
    r = requests.post(url, headers = {"Authorization": "Bearer "+ token, "Content-Type":"application/gzip","Accept":"application/json"}, data= open(package, 'rb'), verify=False)
    if (r.status_code != 200 and r.status_code != 201 and r.status_code != 202):
        raise Exception(r.json()["detail"])
    print(package,"Uploaded successfully\n")
    return r.json()["id"]


def call_shell(param_string):
    try:
        subprocess.check_call(['chmod +x main.sh'], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        program_name = "./main.sh"
        arguments = [variables.config["Config_files"]["Config_file"] ,variables.config["Config_files"]["Vnfd_template"], variables.config["Config_files"]["Nsd_template"], variables.config["Config_files"]["Json_config"], variables.config["Config_files"]["Flavor_config"], param_string]
        command = [program_name]
        command.extend(arguments)
        if(len(arguments) == 6):
            for i in range(0,len(arguments)-1):
                if not os.path.exists(arguments[i]):
                    raise Exception("The following file path doesnt exist",arguments[i])
            output = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)
            print(output.communicate()[0])
        else:
            raise SystemExit("Error=Arguments list doesn't match the required\n")
    except Exception as e:
        raise SystemExit('Error occured =',e)

def vnfd_upload(vnfd_packages): # Upload VNFD package
    print("Uploading the VNFD Packages\n")
    token = auth_token()
    vnfd_id = []
    for i in range(0,len(vnfd_packages)):
        vnfd_id.append(package_upload(vnfd_packages[i],token,"vnfd"))
    return vnfd_id

def nsd_upload(nsd_packages): # Upload NSD package
    print("Uploading the NSD Packages\n")
    token = auth_token()
    for i in range(0,len(nsd_packages)):
        return package_upload(nsd_packages[i],token,"nsd")
    #nsd_package = nsd_pacakges
    #return package_upload(nsd_package,token,"nsd")

def nsdcreate(nsfile, ns_dir):
    try:
        os.mkdir(ns_dir)
        os.replace(nsfile, ns_dir+"/"+nsfile)
        program_name = "tar"
        arguments = ["-czvf", ns_dir+".tar.gz", ns_dir]
        command = [program_name]
        command.extend(arguments)
        output = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)
        if output.returncode:
            raise Exception("Package build failed=",output.communicate()[0])
    except Exception as e:
        raise SystemExit('Error occured =',e)
