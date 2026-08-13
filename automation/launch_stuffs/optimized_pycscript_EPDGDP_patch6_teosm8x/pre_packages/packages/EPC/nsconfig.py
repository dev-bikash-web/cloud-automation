import json
import variables
import common


def change_json(mydict):
    try:
        for ip_key,ip_value in mydict.items():
            value = ""
            with open("lte_epc.cfg", 'r') as fp:
                content = fp.read().split("\n")
                for key in content:
                    if ip_value in key.split("=")[0]:
                        value = key.split("=")[1]
            for vnf in variables.ns_template_structure.keys():
                if value != "":
                    #print(ip_key,ip_value,value)
                    if ip_key in variables.json_file[vnf]["ns"]:
                        variables.json_file[vnf]["ns"][ip_key] = value
        with open(variables.config["Config_files"]["Json_config"],"w") as f:
            json.dump(variables.json_file, f, indent=8, separators=(',', ': '))
    except Exception as e:
        raise SystemExit('Not able to populate json for NS parameters. Error  =',e)

def populate_json():
    change_json(variables.ips)
    change_json(variables.ip6s)
    change_json(variables.netname)

