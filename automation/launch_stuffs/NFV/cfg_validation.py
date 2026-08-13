#!/usr/bin/env python3

# Script: cfg_config.py
# Author: CFW Team
#
# Purpose:

import configparser
import os
import time
import sys
import ipaddress

CFG_FILE = "cfw_config.cfg"
NEW_FILE = "xyz"
SEPARATOR = "##***NODE CONFIG STARTS HERE***##"

mandatory_sections = ["default",
                      "ssh",
                      "tacacs",
                      "sts",
                      "ipdr",
                      "hamon_reporter",
                      "snmp",
                      "ntp",
                      "os_hardening",
                      "backup_restoration",
                      "syslog",
                      "fast_path_if_",
                      "hamon_chain",
                      "sys_path_if_",
                      "static_route_ipv4_",
                      "CFG_VERSION",
                      ##for dpi
                      "dpi_",
                      "hamon_chain",
                      ##for epdglb
                      "lb_global_config",
                      "lb_config_",
                      ##for secgw
                      "secgw-ha",
                      ##for cgnat
                      "cgnat44_",
                      ##for firewall
                      "firewall_default",
                      "fwruleset_",
                      "zone_creation_",
                      "local_zone_creation_",
                      #for twagdp
                      "deployment_mode",
                      "twagdp_config",
                      ##for imsdp
                      "imsdp",
                      "pod_",
                      ##for cips
                      "update_cips_sig",
                      "cips_",
                      ##for epdgdp
                      "epdg_config",
                      "epdg_pcscf_",
                      "epdg_imsdp_",
                      "epdg_pgwdp_"
                      ]

mandatory_parameters = {
    "default": ["node-name", "mgmt-ipv4", "mgmt-gw-ipv4", "ctrl-ipv4", "ctrl-gw-ipv4", "ctrl-interface-name"],
    "ssh": ["port"],
    "tacacs": ["tacacs-server-ipv4", "port", "password"],
    "sts": ["control-address-ipv4",
            "control-port",
            "data-address-ipv4",
            "data-port",
            "self-ipv4",
            "access-interface",
            "pdn-interface"],
    "l2tp_sts": ["access-interface", "pdn-interface"],
    "ipdr": ["host-server-ipv4", "port"],
    "hamon_reporter": ["dpi-ipv4"],
    "snmp": ["trap-target-ipv4"],
    "ntp": ["ntp-server-ipv4", "min-poll", "max-poll"],
    "os_hardening": ["login-attempts",
                     "login-duration",
                     "login-session-timeout",
                     "password-length",
                     "password-min-class",
                     "max-sessions"],
    "backup_restoration": ["host-ipv4"],
    "syslog": ["host-ipv4", "port"],
    "fast_path_if_": ["if_name", "vlan_id", "if-ipv4"],
    "hamon_chain": ["firewall", "cips", "cgnat"],
    "sys_path_if_": ["if_name", "vlan_id", "if-ipv4"],
    "static_route_ipv4_": ["route-ipv4", "next-hop-ipv4"],
    "static_route_ipv6_": ["route-ipv6", "next-hop-ipv6"],
    "CFG_VERSION": ["version"],
    "vrf_": ["name", "type", "description"],
    ##for dpi
    "dpi_": ["cpms-ipv4", "cpms_region_code", "dpi_reported_name", "dpi_reported_name", "cpms_passwd", "1_pgw-mgmt-ipv4", "pgw-dpi-interface_1"],
    ##for epdg-lb
    "lb_global_config": ["gc-cpu-affinity", "ike-init-timeout", "ike-spi-timeout", "ipp-timeout", "esp-spi-timeout", "bgp-asn"],
    "lb_config_": ["bgp-asn", "bgp-update-source-ipv4", "cluster-ipv4", "cluster-name", "node1-ipv4", "bgp-node1-asn"],
    ##for sec-gw
    "secgw-ha": ["management-if", "management-vrrp-group", "management-ipv4", "enb-if", "enb-vlan", "enb-vrrp-group", "enb-ipv4", "mme-if", 
                 "mme-vlan", "mme-vrrp-group", "mme-ipv4", "sync-if", "sync-vlan", "sync-group", "local-ipv4", "remote-ipv4", "internal-mgmt-if-ipv4", 
                 "internal-enb-if-ipv4", "internal-sync-if-ipv4", "internal-mme-if-ipv4"],
    ##for cgnat
    "cgnat44_": ["pool-name", "pool-ip-start-ipv4", "pool-ip-end-ipv4", "pool-port-start", "pool-port-end", "port-overloading", "ue-ip-start-ipv4", 
                 "ue-ip-end-ipv4", "policy-interface", "logging"],
    "cgnat64_": ["pool-name", "pool-ip-start-ipv4", "pool-ip-end-ipv4", "pool-port-start", "pool-port-end", "port-overloading", "ue-ip-start-ipv6", 
                 "ue-ip-end-ipv6", "policy-interface", "logging"],
    "cgnat64-Passthrough_": ["ue-ip-start-ipv6", "ue-ip-end-ipv6", "policy-interface", "logging"],
    "cgnat44-Passthrough_": ["ue-ip-start-ipv4", "ue-ip-end-ipv4", "policy-interface", "logging"],
    ##for firewall
    "fw_attached_to_interface_": ["interface-name", "vlan", "direction", "fw-name"],
    "zone_creation_": ["zone-name", "zone-interface"],
    "zone_communication_": ["from-zone", "to-zone", "fwruleset"],
    ##for twagdp
    "deployment_mode": ["access-mode"],
    "twagdp_config": ["twagcp-ipv4", "twagcp-node1-ipv4", "twagcp-node2-ipv4"],
    ##for imsdp
    "imsdp": ["num-pods", "logging", "max-bandwidth", "max-flowpair", "imscp-worker-ip", "li-server-ip", "transcoder-cp-ipv4", "transcoder-dp-ipv4"], 
    "pod_":["media-start-ipv4", "media-end-ipv4", "media-start-port", "media-end-port"],
    ##for cips
    "cips_": ["deployment", "cpu-count", "protected-network-ipv4", "src-name", "src-url", "whitelist-interface1", "whitelist-interface2", "logging","cips-signature-vm-ipv4"],
    ##for lac
    "lac": ["logging-debug", "logging-file", "logging-session","logging-syslog", "pgw-address-ipv4", "pgw-port", "self-address-ipv4", "self-port", "session-id-end", 
            "session-id-start", "session-timeout", "tunnel-timeout", "max-session-supported", "max-tunnel-supported"],
    ##for epdgdp
    "epdg_config": ["epdgcp-ipv4", "epdgcp-node1-ipv4", "epdgcp-node2-ipv4", "maximum-subscriber", "home_plmn_mcc", "home_plmn_mnc"],
    "epdg_pcscf_": ["pcscf-subnet"],
    "epdg_imsdp_": ["imsdp-subnet"],
    "epdg_pgwdp_": ["pgwdp-subnet", "next-hop-ipv4"]
}

int_parameters = ["port", "control-port", "data-port", "min-poll", "max-poll", "login-attempts", "login-duration",
                  "login-session-timeout", "password-length", "password-min-class", "max-sessions", "vlan_id",
                  "pool-port-start", "pool-port-end", "cpms_region_code",
                  "no-of-rules", "rule-1", "rule-2" , "no-of-zone", "no-of-local-zone",
                  "no-of-zone-communication", "management-vrrp-group", "enb-vrrp-group", "mme-vrrp-group", "sync-vlan",
                  "sync-vrrp-group", "cpu-count","sts-control-port", "syslog-port", "ssh-port", "local-ssh-port",
                  "tcp-specfic-port", "udp-specfic-port", "conn-connection-no", "cpu-count","gtp-port","ike-port",
                  "rule-number", "src-port", "dst-port", "vlan"]

ext_servers = {
    "snmp" : ["trap-target-ipv4"],
    "tacacs_1" : ["tacacs-server-ipv4"],
    "sts" : ["control-address-ipv4", "data-address-ipv4"], #control address and data address
    "ipdr_1" : ["host-server-ipv4"],
    "syslog_1" : ["host-ipv4"],
    "ntp_1" : ["ntp-server-ipv4"],
    "neighbor_bgp_1" : ["neighbor-ipv4", "neighbor-ipv6"],
    "backup_restoration" : ["host-ipv4"]
}


def create_config_parser_input(cfg_nfv, cfg_parser):
    ################################################
    with open(cfg_nfv, "r") as fp:
        config_text = fp.readlines()
        fp.close()
    ################################################
    new_fp = open(cfg_parser, "w")
    write = False

    for line in config_text:
        if write == True:
            new_fp.write(line)

        if line.strip() == SEPARATOR:
            write = True
    ################################################
    new_fp.close()


def check_for_mandatory_sections(config):
    ret = True
    if config.get("default", "node-name") != "dpi":
        mandatory_sections.remove("dpi_")
        mandatory_sections.remove("hamon_chain")
        mandatory_parameters.pop("dpi_")
    if config.get("default", "node-name") != "epdgdplb":
        mandatory_sections.remove("lb_global_config")
        mandatory_sections.remove("lb_config_")
        mandatory_parameters.pop("lb_global_config")
        mandatory_parameters.pop("lb_config_")
    if config.get("default", "node-name") != "secgw":
        mandatory_sections.remove("secgw-ha")
        mandatory_parameters.pop("secgw-ha")
    if config.get("default", "node-name") != "cgnat":
        mandatory_sections.remove("cgnat44_")
        mandatory_parameters.pop("cgnat44_")
        mandatory_parameters.pop("cgnat64_")
        mandatory_parameters.pop("cgnat44-Passthrough_")
        mandatory_parameters.pop("cgnat64-Passthrough_")
    if config.get("default", "node-name") != "firewall":
        mandatory_sections.remove("firewall_default")
        mandatory_sections.remove("fwruleset_")
        mandatory_sections.remove("zone_creation_")
        mandatory_sections.remove("local_zone_creation_")
        mandatory_parameters.pop("fw_attached_to_interface_")
        mandatory_parameters.pop("zone_creation_")
        mandatory_parameters.pop("zone_communication_")
    if config.get("default", "node-name") != "twagdp":
        mandatory_sections.remove("deployment_mode")
        mandatory_sections.remove("twagdp_config")
        mandatory_parameters.pop("deployment_mode")
        mandatory_parameters.pop("twagdp_config")
        mandatory_parameters["default"].remove("ctrl-ipv4")
        mandatory_parameters["default"].remove("ctrl-gw-ipv4")
        mandatory_parameters["default"].remove("ctrl-interface-name")
    if config.get("default", "node-name") != "imsdp":
        mandatory_sections.remove("imsdp")
        mandatory_sections.remove("pod_")
        mandatory_parameters.pop("imsdp")
        mandatory_parameters.pop("pod_")
    if config.get("default", "node-name") != "cips":
        mandatory_sections.remove("cips_")
        mandatory_sections.remove("update_cips_sig")
        mandatory_parameters.pop("cips_")
    if config.get("default", "node-name") != "epdgdp":
        mandatory_sections.remove("epdg_config")
        mandatory_sections.remove("epdg_pcscf_")
        mandatory_sections.remove("epdg_imsdp_")
        mandatory_sections.remove("epdg_pgwdp_")
        mandatory_parameters.pop("epdg_config")
        mandatory_parameters.pop("epdg_pcscf_")
        mandatory_parameters.pop("epdg_imsdp_")
        mandatory_parameters.pop("epdg_pgwdp_")
    if config.get("default", "node-name") == "cips":
        mandatory_sections.remove("fast_path_if_")
        mandatory_sections.remove("ipdr")
    if config.get("default", "node-name") == "secgw":
        mandatory_sections.remove("ipdr")
        mandatory_sections.remove("hamon_reporter")
    if config.get("default", "node-name") == "dpi":
        mandatory_sections.remove("hamon_reporter")
    if config.get("default", "node-name") == "imsdp" or config.get("default", "node-name") == "ibcfdp":
        mandatory_sections.remove("hamon_reporter")
        mandatory_sections.remove("syslog")
        mandatory_sections.remove("ipdr")
        mandatory_sections.remove("tacacs")
        mandatory_sections.remove("backup_restoration")
        mandatory_parameters["sts"].remove("access-interface")
        mandatory_parameters["sts"].remove("pdn-interface")
    if config.get("default", "node-name") == "hhe":
        mandatory_sections.remove("sts")
        mandatory_sections.remove("ipdr")
        mandatory_sections.remove("hamon_reporter")
        mandatory_sections.remove("syslog")
        mandatory_sections.remove("fast_path_if_")
        mandatory_sections.remove("tacacs")
    if config.get("default", "node-name") not in ["dpi","secgw"]:
        mandatory_sections.remove("hamon_chain")
    if config.get("default", "node-name") not in ["hhe"]:
        mandatory_sections.remove("sys_path_if_")
    if config.get("default", "node-name") == "epdgdp":
        mandatory_sections.remove("hamon_reporter")
        mandatory_sections.remove("sts")
        mandatory_sections.remove("ipdr")
        mandatory_sections.remove("os_hardening")
    if config.get("default", "node-name") == "epdgdplb":
        mandatory_sections.remove("hamon_reporter")
        mandatory_sections.remove("sts")
        mandatory_sections.remove("ipdr")
    if config.get("default", "node-name") == "twagdp":
       mandatory_sections.remove("hamon_reporter")
       mandatory_sections.remove("sts")
       mandatory_sections.remove("ipdr")
       mandatory_sections.remove("backup_restoration")
       mandatory_sections.remove("syslog")
       mandatory_sections.remove("tacacs")
        

    for key in mandatory_sections:
        count = 0
        for section in config.sections():
            if section.startswith(key):
                count += 1
        if count == 0:
            ret = False
            print(f"Please enter mandatory section \"{key}\"")
    return ret


def check_for_mandatory_parameters(config):
    ret = True
    node_name = config.get("default", "node-name")
    for key in mandatory_parameters:
        for section in config.sections():
            if section.startswith(key):
                for parameter in mandatory_parameters[key]:
                    count = 0
                    if (node_name == "dpi" and section == "fast_path_if_3" and
                            parameter == "vlan_id"):
                        continue
                    for opt in config.options(section):
                        if opt.startswith(parameter):
                            count += 1
                    if count == 0:
                        print(f"Please enter mandatory field \"{parameter}\" in section \"{section}\"")
                        ret = False
    return ret


def is_valid_ipv4(ip):
    parts = ip.split('/')
    if len(parts) > 2:
        return False
    elif len(parts) == 2:
        subnet = parts[1]
        if not subnet.isdigit() or not 0 <= int(subnet) <= 32:
            return False

    octets = parts[0].split('.')
    if len(octets) != 4:
        return False
    else:
        for octet in octets:
            if not octet.isdigit() or not 0 <= int(octet) <=255:
                return False
    return True


def is_valid_ipv6(ip):
    parts = ip.split('/')
    if len(parts) > 2:
        return False
    elif len(parts) == 2:
        subnet = parts[1]
        if not subnet.isdigit() or not 0 <= int(subnet) <= 128:
            return False

    try:
        ipaddress.IPv6Address(parts[0])
        return True
    except ipaddress.AddressValueError:
        return False


def validate_ip_addresses(config):
    ret =True
    for section in config.sections():
        for option, value in config.items(section):
            if option.endswith("-ipv4") and not is_valid_ipv4(value):
                print(f"Please enter valid ipv4 against parameter \"{option}\" in section \"{section}\"")
                ret = False
            elif option.endswith("-ipv6") and not is_valid_ipv6(value):
                print(f"Please enter valid ipv6 against parameter \"{option}\" in section \"{section}\"")
                ret = False
    return ret


def check_parameter_type(config):
    ret = True
    for section in config.sections():
        for option, value in config.items(section):
            if option in int_parameters and not value.isdigit():
                print(f"Please enter valid integer for parameter \"{option}\" in section \"{section}\"")
                ret = False
            elif option in int_parameters and "port" in option and not 0< int(value) <=65535:
                print(f"Please enter port in \"{option}\" in section \"{section}\" in the range [1,65535]")
                ret = False
    return ret


def validate_vrf(config):
    ret = True
    vrf_list = []
    for section in config.sections():
        if section.startswith("vrf"):
            if config.has_option(section, "name"):
                vrf_list.append(config.get(section, "name"))
            else:
                print(f"Please enter vrf name in vrf section \"{section}\"")
                return False
    
    for section in config.sections():
        if section.startswith("fast_path_if_") or section.startswith("sys_path_if_") or section.startswith("static_route"):
            if config.has_option(section, "vrf_name") and config.get(section, "vrf_name") not in vrf_list:
                print(f"Please enter vrf name from vrf sections provided in cfg\n")
                ret = False

    return ret


def if_routes_exists(config):
    ret = True
    routes = []
    for section in config.sections():
        if section.startswith("static_route"):
            if config.has_option(section, "route-ipv4") and (ipaddress.ip_network(config.get(section, "route-ipv4")) != ipaddress.ip_network("0.0.0.0/0")):
                routes.append(config.get(section, "route-ipv4"))
            if config.has_option(section, "route-ipv6") and (ipaddress.ip_network(config.get(section, "route-ipv6")) != ipaddress.ip_network("0::0/0")):
                routes.append(config.get(section, "route-ipv6"))

    for server, ip_list in ext_servers.items():
        if config.has_section(server):
            for ip in ip_list:
                ip_addr = config.get(server, ip).split('/')[0]
                ans = False
                for subnet in routes:
                    if (is_valid_ipv4(ip_addr) and is_valid_ipv4(subnet)) or (is_valid_ipv6(ip_addr) and is_valid_ipv6(subnet)):
                        if ipaddress.ip_address(ip_addr) in ipaddress.ip_network(subnet):
                            ans = True
                if ans == False:
                    print(f"Please enter static route for section \"{server}\" to reach ip \"{ip}\" \n")
                    ret = False
        else:
            continue

    return ret


def check_cgnat_specific(config):
    ret = True
    for section in config.sections():
        if section.startswith("cgnat"):
            #1 pool-ip-start-ipv4 <= pool-ip-end-ipv4
            if config.has_option(section, "pool-ip-start-ipv4") and config.has_option(section, "pool-ip-end-ipv4"):
                ip1 = config.get(section, "pool-ip-start-ipv4")
                ip2 = config.get(section, "pool-ip-end-ipv4")
                ip_addr1 = ipaddress.ip_address(ip1)
                ip_addr2 = ipaddress.ip_address(ip2)
                if ip_addr1 > ip_addr2:
                    print(f"Please enter \"pool-ip-start-ipv4\" smaller or equal to \"pool-ip-end-ipv4\" in section \"{section}\"")
                    ret = False

            #2 pool-port-end - pool-port-start >= 64
            if config.has_option(section, "pool-port-end") and config.has_option(section, "pool-port-start"):
                port_diff = int(config.get(section, "pool-port-end")) - int(config.get(section, "pool-port-start"))
                if port_diff < 64:
                    print(f"Please enter \"pool-port-end\" and \"pool-port-start\" in section \"{section}\" such that \"pool-port-end\" must be atleast 64 bytes greater than \"pool-port-start\"")
                    ret = False

            #3 ue-ip-start-ipv4 <= ue-ip-end-ipv4 (first check if exists)
            if config.has_option(section, "ue-ip-start-ipv4") and config.has_option(section, "ue-ip-end-ipv4"):
                ip1 = config.get(section, "ue-ip-start-ipv4")
                ip2 = config.get(section, "ue-ip-end-ipv4")
                ip_addr1 = ipaddress.ip_address(ip1)
                ip_addr2 = ipaddress.ip_address(ip2)
                if ip_addr1 > ip_addr2:
                    print(f"Please enter \"ue-ip-start-ipv4\" smaller or equal to \"ue-ip-end-ipv4\" in section \"{section}\"")
                    ret = False

            #4 ue-ip-start-ipv6 <= ue-ip-end-ipv6 (first check if exists)
            if config.has_option(section, "ue-ip-start-ipv6") and config.has_option(section, "ue-ip-end-ipv6"):
                ip1 = config.get(section, "ue-ip-start-ipv6")
                ip2 = config.get(section, "ue-ip-end-ipv6")
                ip_addr1 = ipaddress.ip_address(ip1)
                ip_addr2 = ipaddress.ip_address(ip2)
                if ip_addr1 > ip_addr2:
                    print(f"Please enter \"ue-ip-start-ipv6\" smaller or equal to \"ue-ip-end-ipv6\" in section \"{section}\"")
                    ret = False

    return ret

def check_firewall_specific(config):
    ret = True
    port_protocols = ['tcp', 'udp']  # Protocols that support port matching

    for section in config.sections():
        if section.startswith("fwruleset_"):
            # 1. Validate optional src-ipv4, src-ipv6, dst-ipv4, dst-ipv6 if present
            has_src_ipv4 = config.has_option(section, 'src-ipv4')
            has_src_ipv6 = config.has_option(section, 'src-ipv6')
            has_dst_ipv4 = config.has_option(section, 'dst-ipv4')
            has_dst_ipv6 = config.has_option(section, 'dst-ipv6')

            if has_src_ipv4:
                src_ipv4 = config.get(section, 'src-ipv4')
                if not is_valid_ipv4(src_ipv4):
                    print(f"Please enter valid IPv4 address against parameter \"src-ipv4\" in section \"{section}\"")
                    ret = False
                if not has_dst_ipv4:
                    print(f"Please enter valid IPv4 address against parameter \"dst-ipv4\" in section \"{section}\"")
                    ret = False

            if has_src_ipv6:
                src_ipv6 = config.get(section, 'src-ipv6')
                if not is_valid_ipv6(src_ipv6):
                    print(f"Please enter valid IPv6 address against parameter \"src-ipv6\" in section \"{section}\"")
                    ret = False
                if not has_dst_ipv6:
                    print(f"Please enter valid IPv6 address against parameter \"dst-ipv6\" in section \"{section}\"")
                    ret = False

            if has_dst_ipv4:
                dst_ipv4 = config.get(section, 'dst-ipv4')
                if not is_valid_ipv4(dst_ipv4):
                    print(f"Please enter valid IPv4 address against parameter \"dst-ipv4\" in section \"{section}\"")
                    ret = False
                if not has_src_ipv4:
                    print(f"Please enter valid IPv4 address against parameter \"src-ipv4\" in section \"{section}\"")
                    ret = False

            if has_dst_ipv6:
                dst_ipv6 = config.get(section, 'dst-ipv6')
                if not is_valid_ipv6(dst_ipv6):
                    print(f"Please enter valid IPv6 address against parameter \"dst-ipv6\" in section \"{section}\"")
                    ret = False
                if not has_src_ipv6:
                    print(f"Please enter valid IPv6 address against parameter \"src-ipv6\" in section \"{section}\"")
                    ret = False

            # 2. Validate optional protocol if present
            protocol_set = config.has_option(section, 'protocol')
            if protocol_set:
                protocol_value = config.get(section, 'protocol').lower()
                if protocol_value not in ['tcp', 'udp', 'icmp']:
                    print(f"Please enter valid protocol (tcp/udp/icmp) in section \"{section}\"")
                    ret = False

            # 3. Validate optional src-port and dst-port if present
            src_port_set = config.has_option(section, 'src-port')
            dst_port_set = config.has_option(section, 'dst-port')

            if src_port_set or dst_port_set:
                if protocol_set:
                    protocol_value = config.get(section, 'protocol').lower()
                    if protocol_value not in port_protocols:
                        print(f"Error: Section \"{section}\" has source or destination port set, but protocol is \"{protocol_value}\". Only tcp or udp are allowed for port matching.")
                        ret = False
                else:
                    print(f"Error: Section \"{section}\" has source or destination port set but no protocol specified. Please provide a valid protocol.")
                    ret = False

            # 4. Validate optional state if present
            if config.has_option(section, 'state'):
                state_value = config.get(section, 'state').lower()
                if state_value not in ['enable', 'disable']:
                    print(f"Please enter valid state (enable/disable) in section \"{section}\"")
                    ret = False

    # 5. Validate that interfaces/sub-interfaces with attached firewalls are not attached to zones
    fw_interfaces = set()
    for section in config.sections():
        if section.startswith("fw_attached_to_interface_"):
            if config.has_option(section, "interface-name"):
                iface = config.get(section, "interface-name")
                if config.has_option(section, "vlan"):
                    vlan = config.get(section, "vlan")
                    fw_interfaces.add(f"{iface}.{vlan}")
                else:
                    fw_interfaces.add(iface)

    zone_interfaces = {}
    for section in config.sections():
        if section.startswith("zone_creation_"):
            if config.has_option(section, "zone-interface"):
                zone_iface = config.get(section, "zone-interface")
                zone_interfaces[zone_iface] = section

    for iface in fw_interfaces:
        if iface in zone_interfaces:
            zone_sec = zone_interfaces[iface]
            print(f"Error: Interface \"{iface}\" has a firewall attached, so it cannot be attached to a zone in section \"{zone_sec}\"")
            ret = False

    return ret

def main():
    ################################################
    global CFG_FILE
    
    if len(sys.argv) < 3:
        print("provide node name and cfg version as arguments while calling validation")
        sys.exit(1)

    CFG_VERSION = sys.argv[2]

    if sys.argv[1] == "cips":
        CFG_FILE = "idp_config.cfg"
    elif sys.argv[1] == "imsdp":
        CFG_FILE = "imsdp_config.cfg"
    elif sys.argv[1] == "epdgdp" or sys.argv[1] == "twagdp":
        CFG_FILE = "wigw_config.cfg"
    elif sys.argv[1] == "epdgdplb":
        CFG_FILE = "epdgdplb_config.cfg"
    elif sys.argv[1] == "hhe":
        CFG_FILE = "hhe_config.cfg"


    create_config_parser_input(CFG_FILE, NEW_FILE)
    config = configparser.ConfigParser()

    try:
        config.read(NEW_FILE)

    except configparser.DuplicateSectionError as exception:
        section_name = exception.section
        print(f"Please refrain from entering same section more than once.\nDuplicate section detected : \"{section_name}\"")
        sys.exit(1)

    except configparser.DuplicateOptionError as exception:
        section_name = exception.section
        option_name = exception.option
        print(f"Please refrain from entering multiple option with name \"{option_name}\" in section \"{section_name}\"")
        sys.exit(1)

    except configparser.ParsingError as exception:
        wrong_line = exception.line
        print(f"Please adher to the config file syntax. Syntax error for line \"{wrong_line}\"")
        sys.exit(1)

    except configparser.Error as exception:
        print(f"Error occured while Parsing cfw_config.cfg : {exception}")
        sys.exit(1)

    if config.has_section("CFG_VERSION"):
        if config.has_option("CFG_VERSION", "version"):
            if config.get("CFG_VERSION",'version') != CFG_VERSION:
                print(f"CFG Version not in sync!! Please procedd with correct version of CFG")
                sys.exit(1)
        else:
            print(f"Please enter mandatory field \"version\" in section \"CFG_VERSION\"")
            sys.exit(1)
    else:
        print(f"Please enter mandatory section \"CFG_VERSION\" and specify version of cfg used")
        sys.exit(1)
    
    if config.has_option("default", "load-balancer-ipv4") and not config.has_option("default", "lo-ipv4"):
        print("Please add loopback address in CFG file")
        sys.exit(1)

    validations = [
    check_for_mandatory_sections,
    validate_ip_addresses,
    check_parameter_type,
    check_cgnat_specific,
    check_for_mandatory_parameters,
    check_firewall_specific,
    validate_vrf,
    if_routes_exists
    ]

    result = True
    for func in validations:
        if not func(config):
            result = False
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
