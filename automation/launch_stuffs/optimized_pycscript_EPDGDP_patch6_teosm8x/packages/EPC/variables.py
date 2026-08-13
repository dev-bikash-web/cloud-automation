import configparser
import json

config = configparser.ConfigParser()
config.read("creds.cfg")

with open(config["Config_files"]["Json_config"], 'r') as fp:
    json_file = json.load(fp)

ns_template_structure = {}
# eg : ns_template_structure = {"enum_node1" : 1, "enum_node2" :1}
nsd_nos = {}
# eg : nsd_nos = {"nsd" : ["enum_node1","enum_node2"]}

vnfd_packages = []
nsd_packages = []


# Node specific variables

ips = {"pcrf_cp_node1_IP1" : "PCRF_NODE1_PHYSICAL_IPV4", "mme_cp_node1_IP1" : "MME_NODE1_PHYSICAL_IPV4", "sgw_cp_node1_IP1" : "SGW_NODE1_PHYSICAL_IPV4", "pgw_cp_node1_IP1" : "PGW_NODE1_PHYSICAL_IPV4", "pcrf_cp_node2_IP1" : "PCRF_NODE2_PHYSICAL_IPV4", "mme_cp_node2_IP1" : "MME_NODE2_PHYSICAL_IPV4", "sgw_cp_node2_IP1" : "SGW_NODE2_PHYSICAL_IPV4", "pgw_cp_node2_IP1" : "PGW_NODE2_PHYSICAL_IPV4", "pgw_dp_node1_IP1" : "PGW_NODE3_PHYSICAL_IPV4", "sgw_dp_node1_IP1" : "SGW_NODE3_PHYSICAL_IPV4", "pgw_dp_node2_IP1" : "PGW_NODE4_PHYSICAL_IPV4", "sgw_dp_node2_IP1" : "SGW_NODE4_PHYSICAL_IPV4", "tce_node1" : "TCE_NODE_PHYSICAL_IPV4"}

ip6s = {"pcrf_cp_node1_V6IP1" : "PCRF_NODE1_PHYSICAL_IPV6", "mme_cp_node1_V6IP1" : "MME_NODE1_PHYSICAL_IPV6", "sgw_cp_node1_V6IP1" : "SGW_NODE1_PHYSICAL_IPV6", "pgw_cp_node1_V6IP1" : "PGW_NODE1_PHYSICAL_IPV6", "pcrf_cp_node2_V6IP1" : "PCRF_NODE2_PHYSICAL_IPV6", "mme_cp_node2_V6IP1" : "MME_NODE2_PHYSICAL_IPV6", "sgw_cp_node2_V6IP1" : "SGW_NODE2_PHYSICAL_IPV6", "pgw_cp_node2_V6IP1" : "PGW_NODE2_PHYSICAL_IPV6", "pgw_dp_node1_V6IP1" : "PGW_NODE3_PHYSICAL_IPV6", "sgw_dp_node1_V6IP1" : "SGW_NODE3_PHYSICAL_IPV6", "pgw_dp_node2_V6IP1" : "PGW_NODE4_PHYSICAL_IPV6", "sgw_dp_node2_V6IP1" : "SGW_NODE4_PHYSICAL_IPV6", "tce_node1" : "TCE_NODE_PHYSICAL_IPV6"}

netname = {"nwkName1" : "PROVIDER_NAME", "nwkName2" : "PROVIDER_DP_NAME"}

