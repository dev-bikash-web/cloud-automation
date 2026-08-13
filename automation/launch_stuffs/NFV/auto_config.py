#!/usr/bin/env python3

# Script: auto_config.py
# Author: CFW Team
#
# Purpose:

import configparser
import os
import time
import sys
import subprocess
import json
from datetime import datetime
import re

CFG_FILE = "cfw_config.cfg"
NEW_FILE = "xyz"
SEPARATOR = "##***NODE CONFIG STARTS HERE***##"
CLI_FILE = "/tmp/nfv_config_conf.cli"
OSH_SCRIPT = "osh_run_all_script.sh"
LOGFILE_PATH = "/var/log/cfw_nfv_configuration.log"
VALIDATION_SCRIPT = "cfg_validation.py"
SYSLOG_RT_BURST_DEFAULT = 100000  #for journal logs
SYSLOG_IPDR_BURST_DEFAULT = 2000000 #for ipdr logs
SYSLOG_RT_INTERVAL_DEFAULT = 1
MSS_DEFAULT = 1300
MTU_DEFAULT = 1400

NODE_SNMP_DISC = None
NODE_SNMP_CTX = None
USER_NAME = None
NODE_MSG_REGEX = []

CGNAT_PRIORITY = 10
EPDGDP_DEFAULT_ACTION = "clear"
EPDGDP_DEFAULT_INTERVAL = 30
EPDGDP_DEFAULT_TIMEOUT = 120
HOSTFW_RULE_NUMBER_MGMT = 100
HOSTFW_RULE_NUMBER_CTRL = 100
if_ipv4 = {}
if_ipv6 = {}

MGMT_IF_NAME = 'eth0'
CTRL_IF_NAME = 'eth1'


def log(msg):
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Open the file in append mode and write the current date and time with msg
    with open(LOGFILE_PATH, 'a') as file:
        file.write(f'{current_datetime} : {msg}')
        if "configure" in msg:
            file.write(f"==================================================================\n")
        elif "commit" in msg:
            file.write(f"==================================================================\n")

def compute_ip_diff( first_ip, last_ip):
    ip_set = set()
    ip_set.add(str(first_ip))
    ip_set.add(str(last_ip))

    # Check the size of the set
    size_of_set = len(ip_set)
    return size_of_set

def compute_engine_id(ip_addr):
    '''
    compute SNMP engine ID
    '''
    ip_addr_str = str(ip_addr)
    # Split the IP address into its parts
    parts = ip_addr_str.split('.')
    hex_value = '0x8000150404'
    # Convert each part to an integer, then to hexadecimal, and concatenate them
    for part in parts:
        hex_value += format(int(part), '02x')
    hex_value += '23a1'
    return hex_value


def generate_node_based_values_and_commands(config, section):
    node_name = config.get(section, 'node-name')
    banner_name = node_name.upper()
    if banner_name == "FIREWALL":
        banner_name = "CFW"
    global NODE_SNMP_CTX
    global NODE_SNMP_DISC
    global NODE_MSG_REGEX
    global USER_NAME
    commands = ""
    commands += f"set system login banner pre-login \"Welcome to {banner_name}\\n\"\n"
    commands += f"set system login banner post-login \"Welcome to {banner_name}\\n\"\n"
    # set history path for eventhandler & enable for dataplane
    if config.get('default', 'node-name') == "imsdp" or config.get('default', 'node-name') == "ibcfdp":
        commands += f"set service event-handler history file /opt/cfw/eventhandler/alarms.log\n"
    else:
        commands += f"set service event-handler history\n"
    commands += f"set service event-handler monitor dataplane enabled\n"
    commands += f"set service event-handler monitor memory\n"
    commands += f"set system coredump storage compress yes\n"
    commands += f"set system coredump storage max-file-size 20G\n"
    commands += f"set system coredump storage total-size 20G\n"
    commands += f"set interfaces system {config.get('default','management-int-name')}\n"

    if node_name not in ["dpi", "firewall"]:
        commands += "set system boot-loader isolated-cpus 2-11\n"
        commands += "set system boot-loader default-smp-affinity 0\n"

    if node_name == "firewall":
        NODE_SNMP_CTX = "cfwSecFwall"
        NODE_SNMP_DISC = "FIREWALL"
        USER_NAME = "cfw"
        NODE_MSG_REGEX.append("'FIREWALL: SESSION_CREATE'")
        NODE_MSG_REGEX.append("'FIREWALL: SESSION_DELETE'")
        commands += "set system boot-loader isolated-cpus 3-9\n"
        commands += "set system boot-loader default-smp-affinity 0\n"
        commands += "set system default dataplane cpu-affinity 3-9\n"
        commands += "set system default dataplane max-rx-queue 7\n"
        commands += "set system default gc cpu-affinity 1\n"
        commands += "set logging fw session publisher syslog\n"
        commands += "set logging fw session sub-class session-creation\n"
        commands += "set logging fw session sub-class session-deletion\n"
        commands += "set logging fw session cpu-affinity 2\n"
        commands += "set system session timeout icmp established 30\n"
        commands += "set system session timeout icmp new 10\n"
        commands += "set system session timeout other established 60\n"
        commands += "set system session timeout other new 20\n"
        commands += "set system session timeout tcp close-wait 10\n"
        commands += "set system session timeout tcp closing 10\n"
        commands += "set system session timeout tcp established 300\n"
        commands += "set system session timeout tcp fin-received 10\n"
        commands += "set system session timeout tcp fin-sent 10\n"
        commands += "set system session timeout tcp fin-wait 10\n"
        commands += "set system session timeout tcp last-ack 10\n"
        commands += "set system session timeout tcp rst-received 10\n"
        commands += "set system session timeout tcp syn-received 30\n"
        commands += "set system session timeout tcp syn-sent 30\n"
        commands += "set system session timeout tcp time-wait 10\n"
        commands += "set system session timeout udp established 90\n"
        commands += "set system session timeout udp new 30\n"
        commands += f"set system vrf limit 16\n"
        commands += f"set system zone limit 16\n"
        commands += "set service ssh disable-host-validation\n"
        commands += "set system alg ftp disable\n"
        commands += "set system alg pptp disable\n"
        commands += "set system alg rpc disable\n"
        commands += "set system alg sip disable\n"
        commands += "set system alg tftp disable\n"
        commands += "set service event-handler monitor firewall session threshold minor 80\n"
        commands += "set service event-handler monitor firewall session threshold major 90\n"
        commands += "set service event-handler monitor firewall session interval 5\n"
        #setting rest key for user cfw for now key is fixed.
        commands += "set service rest user cfw key Fi6FgvDGSnclUu3D6xHo8jwq6RwSZgQy\n"
        return commands

    if node_name == "dpi":
        NODE_SNMP_CTX = "cfwSecDpi"
        NODE_SNMP_DISC = "DPI"
        USER_NAME = "cfw"
        commands += "set system boot-loader isolated-cpus 3-10\n"
        commands += "set system boot-loader default-smp-affinity 0\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_3','if_name')} receive-cpu-affinity 9\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_3','if_name')} transmit-cpu-affinity 9\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_1','if_name')} receive-cpu-affinity 4-8\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_1','if_name')} transmit-cpu-affinity 4-8\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_2','if_name')} receive-cpu-affinity 4-8\n"
        commands += f"set interfaces dataplane {config.get('fast_path_if_2','if_name')} transmit-cpu-affinity 4-8\n"
        commands += "set system default dataplane cpu-affinity 3-9\n"
        commands += "set system default gc cpu-affinity 1\n"
        commands += "set system services notification cpu-affinity 0\n"
        commands += "set system default dataplane max-rx-queue 7\n"
        commands += "set logging dpi flows publisher syslog\n"
        commands += "set logging dpi flows sub-class flow-deleted\n"
        commands += "set logging dpi flows sub-class flow-identified\n"
        commands += "set logging dpi flows cpu-affinity 2\n"
        commands += "set logging dpi flows formatter raw\n"
        commands += "set system session timeout icmp established 30\n"
        commands += "set system session timeout icmp new 10\n"
        commands += "set system session timeout other established 60\n"
        commands += "set system session timeout other new 20\n"
        commands += "set system session timeout tcp close-wait 10\n"
        commands += "set system session timeout tcp closing 10\n"
        commands += "set system session timeout tcp established 300\n"
        commands += "set system session timeout tcp fin-received 10\n"
        commands += "set system session timeout tcp fin-sent 10\n"
        commands += "set system session timeout tcp fin-wait 10\n"
        commands += "set system session timeout tcp last-ack 10\n"
        commands += "set system session timeout tcp rst-received 10\n"
        commands += "set system session timeout tcp syn-received 30\n"
        commands += "set system session timeout tcp syn-sent 30\n"
        commands += "set system session timeout tcp time-wait 10\n"
        commands += "set system session timeout udp established 90\n"
        commands += "set system session timeout udp new 30\n"
        commands += f"set system vrf limit 16\n"
        commands += f"set system zone limit 16\n"
        commands += "set service ssh disable-host-validation\n"
        # commands for hamon-master
        #commands += "systemctl restart cfw-hamon.service\n"
        commands += "set service hamon enabled true\n"
        commands += "set service hamon selfmon min-uptime 30\n"
        commands += "set service hamon selfmon poll-interval 5\n"
        if config.has_section("hamon_chain"):
            if config.get("hamon_chain", "firewall") == "true":
                commands += "set service hamon peermon chain-node firewall count 1\n"
            if config.get("hamon_chain", "cgnat") == "true":
                commands += "set service hamon peermon chain-node cgnat count 1\n"
            if config.get("hamon_chain", "cips") == "true":
                commands += "set service hamon peermon chain-node cips count 1\n"
        commands += "set system alg ftp disable\n"
        commands += "set system alg pptp disable\n"
        commands += "set system alg rpc disable\n"
        commands += "set system alg sip disable\n"
        commands += "set system alg tftp disable\n"
        commands += "set service event-handler monitor tdpi request-reject-rate threshold major 80\n"
        commands += "set service event-handler monitor tdpi request-reject-rate threshold minor 40\n"
        commands += "set service event-handler monitor tdpi ue_ip interval 5\n"
        commands += "set service event-handler monitor tdpi ue_ip threshold major 80\n"
        commands += "set service event-handler monitor tdpi ue_ip threshold minor 40\n"
        commands += "set service event-handler monitor tdpi unmatched-traffic threshold major 80\n"
        commands += "set service event-handler monitor tdpi unmatched-traffic threshold minor 40\n"
        #setting rest key for user cfw for now key is fixed.
        commands += "set service rest user cfw key Fi6FgvDGSnclUu3D6xHo8jwq6RwSZgQy\n"
        return commands


    if node_name == "cgnat":
        NODE_SNMP_CTX = "cfwSecCgnat"
        NODE_SNMP_DISC = "CGNAT"
        USER_NAME = "cfw"
        commands += "set system default dataplane cpu-affinity 2-8\n"
        commands += "set system default dataplane max-rx-queue 6\n"
        commands += "set system default gc cpu-affinity 1\n"
        commands += "set service nat cgnat cpu-affinity event session 3\n"
        commands += "set service nat cgnat log event session\n"
        commands += "set service nat cgnat session-timeout other established 60\n"
        commands += "set service nat cgnat session-timeout other partially-open 20\n"
        commands += "set service nat cgnat session-timeout tcp established 300\n"
        commands += "set service nat cgnat session-timeout tcp partially-closed 10\n"
        commands += "set service nat cgnat session-timeout tcp partially-open 30\n"
        commands += "set service nat cgnat session-timeout udp established 90\n"
        commands += "set service nat cgnat session-timeout udp partially-open 30\n"
        commands += f"set system vrf limit 16\n"
        commands += f"set system zone limit 16\n"
        commands += "set service ssh disable-host-validation\n"
        commands += "set system alg ftp disable\n"
        commands += "set system alg pptp disable\n"
        commands += "set system alg rpc disable\n"
        commands += "set system alg sip disable\n"
        commands += "set system alg tftp disable\n"
        #session events
        commands += "set service event-handler monitor cgnat session threshold minor 80\n"
        commands += "set service event-handler monitor cgnat session threshold major 90\n"
        commands += "set service event-handler monitor cgnat session interval 5\n"
        #subscriber events
        commands += "set service event-handler monitor cgnat subscriber threshold minor 80\n"
        commands += "set service event-handler monitor cgnat subscriber threshold major 90\n"
        commands += "set service event-handler monitor cgnat subscriber interval 5\n"
        #setting rest key for user cfw for now key is fixed.
        commands += "set service rest user cfw key Fi6FgvDGSnclUu3D6xHo8jwq6RwSZgQy\n"
        return commands

    if node_name == "cips":
        NODE_SNMP_CTX = "cfwSecIdp"
        NODE_SNMP_DISC = "CIPS"
        USER_NAME = "cfw"
        return commands

    if node_name == "secgw":
        NODE_SNMP_CTX = "cfwSecSeg"
        NODE_SNMP_DISC = "SECGW"
        USER_NAME = "cfw"
        commands += "set system default dataplane cpu-affinity 2-6\n"
        commands += "set system default dataplane max-rx-queue 5\n"
        commands += "set system default gc cpu-affinity 2\n"
        # commands for hamon-master
        #commands += "systemctl restart cfw-hamon.service\n"
        commands += "set service hamon enabled true\n"
        commands += "set service hamon selfmon min-uptime 30\n"
        commands += "set service hamon selfmon poll-interval 5\n"
        if config.has_section("hamon_chain"):
            if config.get("hamon_chain", "cips") == "true":
                commands += "set service hamon peermon chain-node cips count 1\n"

        return commands

    if node_name == "imsdp" or node_name == "ibcfdp":
        if node_name == "imsdp":
            NODE_SNMP_CTX = "imsDpMpfe"
            NODE_SNMP_DISC = "IMSDP"
            USER_NAME = "imsdp"
        if node_name == "ibcfdp":
            NODE_SNMP_CTX = "ibcfDpMpfe"
            NODE_SNMP_DISC = "IBCFDP"
            USER_NAME = "ibcfdp"
        commands += "set system default dataplane cpu-affinity 2-11\n"
        commands += "set system default dataplane max-rx-queue 10\n"
        commands += "set system default gc cpu-affinity 1\n"
        # control path interface
        if config.has_option('default', 'ctrl-interface-name'):
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} address {config.get('default','ctrl-ipv4')}\n"
        else:
            commands += f"set interfaces system eth1 address {config.get('default','ctrl-ipv4')}\n"
        # imsdp flowpair event
        commands += f"set service event-handler monitor imsdp flowpair threshold minor 80\n"
        commands += f"set service event-handler monitor imsdp flowpair threshold major 90\n"
        commands += f"set service event-handler monitor imsdp flowpair interval 5\n"
        commands += f"set service event-handler monitor imsdp bandwidth threshold minor 80\n"
        commands += f"set service event-handler monitor imsdp bandwidth threshold major 90\n"
        commands += f"set service event-handler monitor imsdp bandwidth interval 5\n"
        commands += f"set protocols static route 0.0.0.0/0 next-hop {config.get(section,'fastpath-gw-ipv4')}\n"
	    # Transcoder DP route
        if config.has_option('imsdp', 'transcoder-dp-ipv4'):
            commands += f"set protocols static route {config.get('imsdp','transcoder-dp-ipv4')}/32 next-hop {config.get(section,'transcoder-dp-gw-ipv4')}\n"
        # Transcoder CP route
        if config.has_option('imsdp', 'transcoder-cp-ipv4'):
            commands += f"set protocols static route {config.get('imsdp','transcoder-cp-ipv4')}/32 next-hop {config.get(section,'ctrl-gw-ipv4')}\n"
        # IMSCP route
        for key in config.options('imsdp'):  # Get all keys under the section 'imsdp'
            if key.startswith('imscp-worker-ip_') and key.endswith('-ipv4'):
                commands += f"set protocols static route {config.get('imsdp', key)}/32 next-hop {config.get(section, 'ctrl-gw-ipv4')}\n"
        # Li server route
        for key in config.options('imsdp'):
            if key.startswith('li-server-ip_') and key.endswith('-ipv4'):
                commands += f"set protocols static route {config.get('imsdp', key)}/32 next-hop {config.get(section, 'mgmt-gw-ipv4')}\n"

        # MGMT traffic block from fastpath
        commands += f"set security ip-packet-filter group MGMT ip-version ipv4\n"
        commands += f"set security ip-packet-filter group MGMT rule 1 action drop\n"
        commands += f"set security ip-packet-filter group MGMT rule 1 match destination ipv4 host {config.get('default','mgmt-ipv4')}\n"
        commands += f"set security ip-packet-filter interface {config.get('fast_path_if_1', 'if_name')} in MGMT\n"
        # CTRL traffic block from fastpath
        ctrl_ipv4 = config.get("default", "ctrl-ipv4")
        ctrl_ipv4_only = ctrl_ipv4.split("/")[0]
        commands += f"set security ip-packet-filter group MGMT rule 2 action drop\n"
        commands += f"set security ip-packet-filter group MGMT rule 2 match destination ipv4 host {ctrl_ipv4_only}\n"
        commands += f"set security ip-packet-filter group MGMT counters count packets\n"
        commands += f"set security ip-packet-filter group MGMT counters sharing per-interface\n"
        commands += f"set security ip-packet-filter group MGMT counters type auto-per-rule\n"
        commands += f"set security ip-packet-filter interface {config.get('fast_path_if_1', 'if_name')} in MGMT\n"
        if config.get("imsdp", "logging").lower() == "enable":
            commands += f"set logging imsdp counters interval 5\n"
            commands += f"set logging imsdp counters publisher syslog\n"
            commands += f"set logging imsdp counters sub-class api-stats\n"
            commands += f"set logging imsdp counters sub-class packet-stats\n"
            commands += f"set logging imsdp cp-api-events publisher syslog\n"
            commands += f"set logging imsdp cp-api-events sub-class capability\n"
            commands += f"set logging imsdp cp-api-events sub-class cp-connection-down\n"
            commands += f"set logging imsdp cp-api-events sub-class flowpair-add\n"
            commands += f"set logging imsdp cp-api-events sub-class flowpair-delete\n"
            commands += f"set logging imsdp cp-api-events sub-class flowpair-update\n"
            commands += f"set logging imsdp cp-api-events sub-class init\n"
            commands += f"set logging imsdp cp-api-events sub-class register\n"
            commands += f"set logging imsdp cp-api-events sub-class tr-connection-down\n"
            commands += f"set logging imsdp cp-api-events sub-class tr-connection-up\n"
            commands += f"set system syslog file syslog_msg.txt archive files 5\n"
            commands += f"set system syslog file syslog_msg.txt archive size 500000\n"
            commands += f"set system syslog file syslog_msg.txt facility syslog\n"
            commands += f"set system syslog file syslog_msg.txt msg regex 'IMSDP: '\n"
        return commands

    if node_name == "hhe":
        NODE_SNMP_CTX = "cfwSecProxy"
        NODE_SNMP_DISC = "HHE"
        USER_NAME = "cfw"
        commands += "set system default dataplane cpu-affinity 2-9\n"
        commands += "set system default dataplane max-rx-queue 8\n"
        commands += "set system default gc cpu-affinity 1\n"
        return commands

    if node_name == "epdgdp":
        NODE_SNMP_CTX = "wigwEpdgDp"
        NODE_SNMP_DISC = "EPDGDP"
        USER_NAME = "cfw"
        if config.has_option("default", "ctrl-interface-name"):
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} address {config.get('default','ctrl-ipv4')}\n"
        else:
            commands += f"set interfaces system {CTRL_IF_NAME} address {config.get('default','ctrl-ipv4')}\n"
        if config.has_option("default", "lo-ipv4"):
            commands += f"set interfaces loopback lo1 address {config.get('default','lo-ipv4')}\n"

        if config.has_option("default", "load-balancer-ipv4"):
            only_lb_ip = config.get("default", "load-balancer-ipv4").split("/")[0]
            only_swu_ip = config.get("fast_path_if_1", "if-ipv4").split("/")[0]
            commands += f"set policy route prefix-list prefix1 rule 1 action permit\n"
            commands += f"set policy route prefix-list prefix1 rule 1 prefix {config.get('default','lo-ipv4')}\n"
            commands += f"set policy route route-map map1 rule 1 action permit\n"
            commands += f"set policy route route-map map1 rule 1 match ip address prefix-list prefix1\n"
            if config.has_option("default", "local_bgp_asn") and config.has_option("default", "remote_bgp_asn"):
                commands += f"set protocols bgp {config.get('default', 'local_bgp_asn')} address-family ipv4-unicast redistribute connected route-map map1\n"
                commands += f"set protocols bgp {config.get('default', 'local_bgp_asn')} neighbor {only_lb_ip} address-family ipv4-unicast soft-reconfiguration inbound\n"
                commands += f"set protocols bgp {config.get('default', 'local_bgp_asn')} neighbor {only_lb_ip} remote-as {config.get('default', 'remote_bgp_asn')}\n"
                commands += f"set protocols bgp {config.get('default', 'local_bgp_asn')} neighbor {only_lb_ip} update-source {only_swu_ip}\n"
                commands += f"set protocols bgp {config.get(section, 'local_bgp_asn')} parameters ebgp-requires-policy disabled\n"
        #setting rest key for user cfw for now key is fixed.
        commands += "set service rest user cfw key Fi6FgvDGSnclUu3D6xHo8jwq6RwSZgQy\n"

        return commands


    if node_name == "twagdp":
        NODE_SNMP_CTX = "wigwTwagDp"
        NODE_SNMP_DISC = "TWAGDP"
        USER_NAME = "cfw"
        if config.has_option("default", "ctrl-interface-name"):
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} address {config.get('default','ctrl-ipv4')}\n"
        else:
            commands += f"set interfaces system eth1 address {config.get('default','ctrl-ipv4')}\n"
        commands +=f"set interfaces bridge br10\n"
        commands +=f"set interfaces bridge br10 ip enable-proxy-arp\n"
        # route for cp and haf.
        commands +=f"set protocols static route {config.get('twagdp_config','twagcp-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')}\n"
        commands +=f"set protocols static route {config.get('twagdp_config','twagcp-node1-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')}\n"
        commands +=f"set protocols static route {config.get('twagdp_config','twagcp-node2-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')}\n"
        commands +=f"set system default dataplane cpu-affinity 2-9\n"
        commands += "set system default dataplane max-rx-queue 8\n"
        # Twagdp Event specific commands
        commands +=f"set service event-handler monitor twagdp ap interval 10\n"
        commands +=f"set service event-handler monitor twagdp ap threshold major 90\n"
        commands +=f"set service event-handler monitor twagdp ap threshold minor 80\n"
        commands +=f"set service event-handler monitor twagdp subscriber interval 10\n"
        commands +=f"set service event-handler monitor twagdp subscriber threshold major 90\n"
        commands +=f"set service event-handler monitor twagdp subscriber threshold minor 80\n"

        return commands


    if node_name == "epdgdplb":
        NODE_SNMP_CTX = "wigwEpdgLbDp"
        NODE_SNMP_DISC = "EPDGDPLB"
        USER_NAME = "cfw"
        if config.has_option("default", "ctrl-interface-name"):
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} address {config.get('default','ctrl-ipv4')}\n"
        return commands

    return commands


def generate_snmp_commands(config, section):
    commands = ""
    commands += f"set service snmp community public context {NODE_SNMP_CTX}\n"
    if config.has_option('snmp', 'listen-address-ipv4'):
        commands += f"set service snmp listen-address {config.get(section,'listen-address-ipv4')}\n"
        commands += f"set service snmp v3 engineid {compute_engine_id(config.get(section,'listen-address-ipv4'))}\n"
    else:
        commands += f"set service snmp listen-address {config.get('default','mgmt-ipv4')}\n"
        commands += f"set service snmp v3 engineid {compute_engine_id(config.get('default','mgmt-ipv4'))}\n"
    commands += "set service snmp community public authorization rw\n"
    commands += "set service snmp community public view public\n"
    commands += f"set service snmp description {NODE_SNMP_DISC}\n"
    commands += "set service snmp view public oid 1.3.6.1\n"
    commands += f"set service snmp v3 user {USER_NAME} auth plaintext-key {USER_NAME}12345\n"
    commands += f"set service snmp v3 user {USER_NAME} auth type md5\n"
    commands += f"set service snmp v3 user {USER_NAME} mode rw\n"
    commands += f"set service snmp v3 trap-target {config.get(section,'trap-target-ipv4')} auth plaintext-key {USER_NAME}12345\n"
    commands += f"set service snmp v3 trap-target {config.get(section,'trap-target-ipv4')} engineid {compute_engine_id(config.get('default','mgmt-ipv4'))}\n"
    commands += f"set service snmp v3 trap-target {config.get(section,'trap-target-ipv4')} type trap\n"
    commands += f"set service snmp v3 trap-target {config.get(section,'trap-target-ipv4')} user {USER_NAME}\n"

    if config.get('default', 'node-name') == "hhe":
        commands += "set service perfmon data-interval 180\n"

    if config.get('default', 'node-name') not in ["hhe","twagdp"]:
        if config.get('default', 'node-name') == 'epdgdp':
            commands += "set service perfmon data-interval 60\n"
        else:
            commands += "set service perfmon data-interval 180\n"
        if config.get('default', 'node-name') == "cips":
            commands += "set system uplink-interface eth1\n"
            commands += "set system downlink-interface eth2\n"
        elif config.get('default', 'node-name') == "imsdp":
            commands += "set system uplink-interface dp0s20\n"
            commands += "set system downlink-interface dp0s21\n"
        elif config.get('default', 'node-name') == "ibcfdp":
            commands += "set system uplink-interface dp0s20\n"
        else:
            if config.has_option(section, 'access-interface'):
                commands += f"set system uplink-interface {config.get('sts', 'access-interface')}\n"
            else:
                commands += "set system uplink-interface dp0s20\n"

            if config.has_option(section, 'pdn-interface'):
                commands += f"set system downlink-interface {config.get('sts', 'pdn-interface')}\n"
            else:
                commands += "set system downlink-interface dp0s21\n"

    if config.get('default', 'node-name') == "twagdp":
        if config.has_option(section, 'access-interface'):
            commands += f"set system uplink-interface {config.get('sts', 'access-interface')}\n"
        else:
            commands += "set system uplink-interface dp0s20\n"
        if config.has_option(section, 'pdn-interface'):
            commands += f"set system downlink-interface {config.get('sts', 'pdn-interface')}\n"
        else:
            commands += "set system downlink-interface dp0s21\n"

    return commands

def generate_tacacs_commands(config, section):
    commands = ""
    #for key, value in items:
    #    commands += f"set system {key} val {value}\n"
    commands += f"set system login tacplus-server {config.get(section,'tacacs-server-ipv4')}\n"
    if config.has_option(section, 'port'):
        commands += f"set system tacplus-options server port {config.get(section, 'port')}\n"
    commands += f"set system tacplus-options server secret {config.get(section,'password')}\n"
    commands += "set system tacplus-options accounting command-start-records\n"
    commands += "set system tacplus-options command-authorization attributes service shell\n"
    commands += "set system tacplus-options command-accounting\n"
    commands += f"set system login auth-chain method tacplus\n"
    commands += f"set system login auth-chain method local\n"
    commands += f"set service event-handler monitor server tacplus address {config.get(section, 'tacacs-server-ipv4')}\n"
    return commands


def generate_sts_commands(config, section):
    commands = ""
    commands += f"set service sts max-session-timeout 150\n"
    commands += f"set service sts max-sessions 5\n"
    commands += f"set service sts server control address {config.get(section,'control-address-ipv4')}\n"
    commands += f"set service sts server control port {config.get(section,'control-port')}\n"
    commands += f"set service sts server data address {config.get(section,'data-address-ipv4')}\n"
    commands += f"set service sts server data port {config.get(section,'data-port')}\n"
    commands += f"set service sts server self-ip {config.get(section,'self-ipv4')}\n"
    if config.get('default', 'node-name') != "imsdp" and config.get('default', 'node-name') != "ibcfdp":
        if config.get('default', 'node-name') in ["cips"]:
            commands += f"set service sts interface access {config.get(section, 'access-interface')}\n"
            commands += f"set service sts interface pdn {config.get(section, 'pdn-interface')}\n"
        else:
            commands += f"set interfaces dataplane {config.get(section,'access-interface')} tel-nw-side access\n"
            commands += f"set interfaces dataplane {config.get(section,'pdn-interface')} tel-nw-side pdn\n"
    if config.get('default', 'node-name') == "imsdp" or config.get('default', 'node-name') == "ibcfdp":
        commands += f"set interfaces dataplane dp0s20 tel-nw-side access\n"
    if config.get("default", "node-name") == "epdgdp":
        commands += f"set service sts gtp-long-header-check true\n"
    return commands


def generate_l2tp_sts_commands(config, section):
    commands = ""
    commands += f"set service sts interface access {config.get(section, 'access-interface')}\n"
    commands += f"set service sts interface pdn {config.get(section, 'pdn-interface')}\n"
    return commands


def generate_ipdr_commands(config, section):
    commands = ""
    if config.get("default", "node-name") in ["dpi","cgnat"]:
        commands += f"set system syslog dp_ipdr_server host {config.get(section,'host-server-ipv4')}:{config.get(section, 'port')} rebind-interval 1024\n"
    else:
        for msg_regex in NODE_MSG_REGEX:
            commands += f"set system syslog host {config.get(section,'host-server-ipv4')}:{config.get(section, 'port')} msg regex {msg_regex}\n"
        commands += f"set system syslog host {config.get(section,'host-server-ipv4')}:{config.get(section, 'port')} protocol udp\n"
    return commands


def generate_hamon_reporter_commands(config, section):
    commands = ""
    #commands += f"systemctl restart cfw-hamon.service\n"
    commands += f"set service hamon enabled true\n"
    commands += f"set service hamon peermon peers {config.get(section,'dpi-ipv4')} max-retries 5\n"
    commands += f"set service hamon selfmon min-uptime 30\n"
    commands += f"set service hamon selfmon poll-interval 5\n"
    commands += f"set protocols static route {config.get(section, 'dpi-ipv4')}/32 next-hop {config.get('default','mgmt-gw-ipv4')}\n"
    return commands


def generate_static_route_ipv4_commands(config,section):
    commands = ""
    if config.has_option(section, 'vrf_name'):
        commands += f"set routing routing-instance {config.get(section,'vrf_name')} protocols static route {config.get(section,'route-ipv4')} next-hop {config.get(section,'next-hop-ipv4')}\n"
    else:
        commands += f"set protocols static route {config.get(section,'route-ipv4')} next-hop {config.get(section,'next-hop-ipv4')}\n"
    return commands

def generate_static_route_ipv6_commands(config,section):
    commands = ""
    if config.has_option(section, 'vrf_name'):
        commands += f"set routing routing-instance {config.get(section,'vrf_name')} protocols static route6 {config.get(section,'route-ipv6')} next-hop {config.get(section,'next-hop-ipv6')}\n"
    else:
        commands += f"set protocols static route6 {config.get(section,'route-ipv6')} next-hop {config.get(section,'next-hop-ipv6')}\n"
    return commands



def generate_ntp_commands(config, section):
    commands = ""
    commands += f"set system ntp server {config.get(section,'ntp-server-ipv4')}\n"
    commands += f"set service event-handler monitor ntp enabled\n"
    commands += f"set system ntp source-interface {config.get('default','management-int-name')}\n"
    if config.has_option(section, 'min-poll'):
        commands += f"set system ntp server {config.get(section,'ntp-server-ipv4')} poll-interval min-poll {config.get(section,'min-poll')}\n"
    else:
        commands += f"set system ntp server {config.get(section,'ntp-server-ipv4')} poll-interval min-poll 3\n"
    if config.has_option(section, 'max-poll'):
        commands += f"set system ntp server {config.get(section,'ntp-server-ipv4')} poll-interval max-poll {config.get(section,'max-poll')}\n"
    else:
        commands += f"set system ntp server {config.get(section,'ntp-server-ipv4')} poll-interval max-poll 3\n"

    return commands


def generate_ssh_commands(config, section):
    commands = ""
    node_name = config.get("default", 'node-name')
    if config.has_option(section, 'port'):
        commands += f"set service ssh port {config.get(section, 'port')}\n"
    if node_name == "epdgdp":
        if config.has_option('default' , 'mgmt-ipv4'):
            commands += f"set service ssh listen-address {config.get('default' , 'mgmt-ipv4')}\n"

    return commands


def generate_os_hardening_commands(config, section):
    commands = ""
    commands += f"set system login auto-disable attempts {config.get(section, 'login-attempts')}\n"
    commands += f"set system login auto-disable duration {config.get(section, 'login-duration')}\n"
    commands += f"set system password requirements length {config.get(section, 'password-length')}\n"
    commands += f"set system password requirements classes min-class {config.get(section, 'password-min-class')}\n"
    commands += f"set system login session-timeout {config.get(section, 'login-session-timeout')}\n"
    commands += f"set system login max-sessions {config.get(section, 'max-sessions')}\n"
    commands += "delete service ssh allow-root\n"

    if os.system(f"grep -q \"^cfw hard maxlogins\" /etc/security/limits.conf"):
        os.system(f"echo \"cfw hard maxlogins 9\" >> /etc/security/limits.conf")
    else:
        os.system(f"sed -i \"s/^cfw hard maxlogins.*/cfw hard maxlogins 9/\" /etc/security/limits.conf")

    if os.system(f"grep -q \"^cfwha hard maxlogins\" /etc/security/limits.conf"):
        os.system(f"echo \"cfwha hard maxlogins 9\" >> /etc/security/limits.conf")
    else:
        os.system(f"sed -i \"s/^cfwha hard maxlogins.*/cfwha hard maxlogins 9/\" /etc/security/limits.conf")

    if os.system(f"grep -q \"^root hard maxlogins\" /etc/security/limits.conf"):
        os.system(f"echo \"root hard maxlogins 9\" >> /etc/security/limits.conf")
    else:
        os.system(f"sed -i \"s/^root hard maxlogins.*/root hard maxlogins 9/\" /etc/security/limits.conf")

    os.system("sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS   60/' /etc/login.defs")
    #OSH_SCRIPT script take care audit,file permission and service related things.
    subprocess.run(["bash", OSH_SCRIPT], cwd="/opt/vyatta/sbin")

    return commands


def generate_syslog_commands(config, section):
    commands = ""
    commands += f"set system syslog host {config.get(section, 'host-ipv4')}:{config.get(section, 'port')} msg regex msg.audit\n"
    log_source_pattern = r'^\\{\"log_source\" : \"eventhandler\"'
    commands += f"set system syslog host {config.get(section, 'host-ipv4')}:{config.get(section, 'port')} msg regex \'{log_source_pattern}\'\n"
    if config.has_option(section, 'interval'):
        commands += f"set system syslog rate-limit interval {config.get(section, 'interval')}\n"
    else:
        commands += f"set system syslog rate-limit interval {SYSLOG_RT_INTERVAL_DEFAULT}\n"
    if config.has_option(section, 'burst'):
        commands += f"set system syslog rate-limit burst {config.get(section, 'burst')}\n"
    else:
        commands += f"set system syslog rate-limit burst {SYSLOG_RT_BURST_DEFAULT}\n"
    commands += f"set service event-handler syslog enabled\n"
    commands += f"set service event-handler monitor server syslog {config.get(section, 'host-ipv4')}\n"
    commands += f"set system syslog rebind-interval 1024\n"
    commands += f"set system syslog udp-rate-limit burst {SYSLOG_IPDR_BURST_DEFAULT}\n"
    commands += f"set system syslog udp-rate-limit interval 10\n"
    return commands


def generate_vrf_commands(config, section):
    commands = ""
    if config.has_option(section, 'type'):
        commands += f"set routing routing-instance {config.get(section, 'name')} instance-type {config.get(section, 'type')}\n"
    if config.has_option(section, 'description'):
        commands += f"set routing routing-instance {config.get(section, 'name')} description {config.get(section, 'description')}\n"
    return commands


def generate_set_interface_commands(config, section):
    commands = ""
    if config.has_option(section , 'vlan_id'):
        commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} address {config.get(section, 'if-ipv4')}\n"
        if config.has_option(section , 'if-ipv6'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} address {config.get(section, 'if-ipv6')}\n"
        if config.has_option(section , 'mss'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} ip tcp-mss limit {config.get(section, 'mss')}\n"
        else:
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} ip tcp-mss limit {MSS_DEFAULT}\n"

        if config.has_option(section , 'mtu'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} mtu {config.get(section, 'mtu')}\n"
        else:
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} mtu {MTU_DEFAULT}\n"
        commands += f"set service event-handler monitor interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}\n"
        ##binding sub-interface to vrf specified
        if config.has_option(section , 'vrf_name'):
            commands +=  f"set routing routing-instance {config.get(section, 'vrf_name')} interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}\n"
    else:
        commands += f"set interfaces dataplane {config.get(section, 'if_name')} address {config.get(section, 'if-ipv4')}\n"
        if config.has_option(section , 'if-ipv6'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} address {config.get(section, 'if-ipv6')}\n"
        if config.has_option(section , 'mss'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} ip tcp-mss limit {config.get(section, 'mss')}\n"
        else:
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} ip tcp-mss limit {MSS_DEFAULT}\n"

        if config.has_option(section , 'mtu'):
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} mtu {config.get(section, 'mtu')}\n"
        else:
            commands += f"set interfaces dataplane {config.get(section, 'if_name')} mtu {MTU_DEFAULT}\n"
        commands += f"set service event-handler monitor interface {config.get(section, 'if_name')}\n"
        ##binding interface to vrf specified
        if config.has_option(section , 'vrf_name'):
            commands +=  f"set routing routing-instance {config.get(section, 'vrf_name')} interface {config.get(section, 'if_name')}\n"

        if config.has_option(section, 'if-gway-ipv4'):
            commands += f"set conduit dp-interface {config.get(section, 'if_name')} gw-address {config.get(section, 'if-gway-ipv4')}\n"
            commands += "set conduit controller-affinity 3\n"
            commands += "set conduit fast-path-affinity 10\n"


    if (
        config.get("default", "node-name") != "imsdp"
        and config.get("default", "node-name") != "ibcfdp"
        and config.get("default", "node-name") != "epdgdp"
        and config.get("default", "node-name") != "twagdp"
    ):

        acl_rule_no = 1
        policy_name_ipv4 = f"{config.get(section, 'if_name')}ipv4"
        policy_name_ipv6 = f"{config.get(section, 'if_name')}ipv6"
        if config.has_option(section , 'vlan_id'):
            policy_name_ipv4 += f"vlan_id{config.get(section, 'vlan_id')}"
            policy_name_ipv6 += f"vlan_id{config.get(section, 'vlan_id')}"

        for ip in if_ipv4.values():
            if acl_rule_no == 1:
                commands += f"set security ip-packet-filter group {policy_name_ipv4} ip-version ipv4\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} action drop\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} match destination ipv4 host {ip}\n"
            acl_rule_no += 1
        if config.has_option('default', 'mgmt-ipv4'):
            if acl_rule_no == 1:
                commands += f"set security ip-packet-filter group {policy_name_ipv4} ip-version ipv4\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} action drop\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} match destination ipv4 host {config.get('default', 'mgmt-ipv4')}\n"


        acl_rule_no = 1
        for ip in if_ipv6.values():
            if acl_rule_no == 1:
                commands += f"set security ip-packet-filter group {policy_name_ipv6} ip-version ipv6\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} action drop\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} match destination ipv6 host {ip}\n"
            acl_rule_no += 1
        if config.has_option('default', 'mgmt-ipv6'):
            if acl_rule_no == 1:
                commands += f"set security ip-packet-filter group {policy_name_ipv6} ip-version ipv6\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} action drop\n"
            commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} match destination ipv6 host {config.get('default', 'mgmt-ipv6')}\n"

        if config.get("default", "node-name") == "hhe":
            if config.has_option(section, "if-ipv4"):
                commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')} in {policy_name_ipv4}\n"
            if config.has_option(section, "if-ipv6"):
                commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')} in {policy_name_ipv6}\n"
        else:
            if config.has_option(section, "if-ipv4"):
                commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')} in {policy_name_ipv4}\n"
            if config.has_option(section, "if-ipv6"):
                commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')} in {policy_name_ipv6}\n"

    return commands


def generate_system_interface_commands(config, section):
    commands = ""
    if config.has_option('default' , 'mgmt-ipv4') and config.get(section, 'if_name') == "hhe":
        commands += f"set interfaces system eth0 address {config.get('default' , 'mgmt-ipv4')}/24\n"
        commands += "set interfaces system eth0 description MGMT-INTERFACE\n"
    if config.has_option(section , 'if-ipv4'):
            if config.has_option(section , 'vlan_id'):
                commands += f"set interfaces system {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} address {config.get(section, 'if-ipv4')}\n"
            else:
                commands += f"set interfaces system {config.get(section, 'if_name')} address {config.get(section, 'if-ipv4')}\n"
    if config.has_option(section , 'if-ipv6'):
            if config.has_option(section , 'vlan_id'):
                commands += f"set interfaces system {config.get(section, 'if_name')} vif {config.get(section, 'vlan_id')} address {config.get(section, 'if-ipv6')}\n"
            else:
                commands += f"set interfaces system {config.get(section, 'if_name')} address {config.get(section, 'if-ipv6')}\n"
    commands += f"set interfaces system {config.get(section, 'if_name')} mtu 1400\n"
    if config.has_option(section , 'status'):
            commands += f"set system {config.get(section, 'status')}-interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}\n"

    acl_rule_no = 1
    policy_name_ipv4 = f"{config.get(section, 'if_name')}ipv4"
    policy_name_ipv6 = f"{config.get(section, 'if_name')}ipv6"
    if config.has_option(section , 'vlan_id'):
        policy_name_ipv4 += f"vlan_id{config.get(section, 'vlan_id')}"
        policy_name_ipv6 += f"vlan_id{config.get(section, 'vlan_id')}"
        if config.has_option(section , 'vrf_name'):
            commands +=  f"set routing routing-instance {config.get(section, 'vrf_name')} interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}\n"
    else:
        if config.has_option(section , 'vrf_name'):
            commands +=  f"set routing routing-instance {config.get(section, 'vrf_name')} interface {config.get(section, 'if_name')}\n"

    for ip in if_ipv4.values():
        if acl_rule_no == 1:
            commands += f"set security ip-packet-filter group {policy_name_ipv4} ip-version ipv4\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} action drop\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} match destination ipv4 host {ip}\n"
        acl_rule_no += 1
    if config.has_option('default', 'mgmt-ipv4'):
        if acl_rule_no == 1:
            commands += f"set security ip-packet-filter group {policy_name_ipv4} ip-version ipv4\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} action drop\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv4} rule {acl_rule_no} match destination ipv4 host {config.get('default', 'mgmt-ipv4')}\n"


    acl_rule_no = 1
    for ip in if_ipv6.values():
        if acl_rule_no == 1:
            commands += f"set security ip-packet-filter group {policy_name_ipv6} ip-version ipv6\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} action drop\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} match destination ipv6 host {ip}\n"
        acl_rule_no += 1
    if config.has_option('default', 'mgmt-ipv6'):
        if acl_rule_no == 1:
            commands += f"set security ip-packet-filter group {policy_name_ipv6} ip-version ipv6\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} action drop\n"
        commands += f"set security ip-packet-filter group {policy_name_ipv6} rule {acl_rule_no} match destination ipv6 host {config.get('default', 'mgmt-ipv6')}\n"

    if config.get("default", "node-name") == "hhe":
        if config.has_option(section, "if-ipv4"):
            commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')} in {policy_name_ipv4}\n"
        if config.has_option(section, "if-ipv6"):
            commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')}.{config.get(section, 'vlan_id')} in {policy_name_ipv6}\n"
    else:
        if config.has_option(section, "if-ipv4"):
            commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')} in {policy_name_ipv4}\n"
        if config.has_option(section, "if-ipv6"):
            commands += f"set security ip-packet-filter interface {config.get(section, 'if_name')} in {policy_name_ipv6}\n"

    return commands


def generate_cgnat44_config_commands(config, section):
    commands = ""
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} address-allocation round-robin\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} address-pooling paired\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} entry A ip-address range start {config.get(section, 'pool-ip-start-ipv4')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} entry A ip-address range end {config.get(section, 'pool-ip-end-ipv4')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port allocation sequential\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port dynamic-block-allocation block-size 64\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port dynamic-block-allocation max-blocks-per-subscriber 8\n"
    if config.get(section, 'port-overloading').lower() == "true":
        commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port overloading enable\n"
    else:
        commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port overloading disable\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port range end {config.get(section, 'pool-port-end')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port range start {config.get(section, 'pool-port-start')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} type CGNAT\n"
    number = section.split('_')[-1]
    ip_count = compute_ip_diff(config.get(section, 'ue-ip-start-ipv4'), config.get(section, 'ue-ip-end-ipv4'))
    #check for same start and end ip
    if ip_count > 1:
        commands += f"set resources group address-group AUTO44_AG{number} address-range {config.get(section, 'ue-ip-start-ipv4')} to {config.get(section, 'ue-ip-end-ipv4')}\n"
    else:
        commands += f"set resources group address-group AUTO44_AG{number} address {config.get(section, 'ue-ip-start-ipv4')}\n"

    commands += f"set service nat cgnat policy AUTO44_CP{number} match source address-group AUTO44_AG{number}\n"
    global CGNAT_PRIORITY
    commands += f"set service nat cgnat policy AUTO44_CP{number} priority {CGNAT_PRIORITY}\n"
    CGNAT_PRIORITY += 10
    commands += f"set service nat cgnat policy AUTO44_CP{number} translation source mapping pool AUTO_{config.get(section, 'pool-name')}\n"
    commands += f"set service nat cgnat policy AUTO44_CP{number} type 44\n"
    commands += f"set service nat cgnat interface {config.get(section,'policy-interface')} policy AUTO44_CP{number}\n"
    if config.get(section, 'logging').lower() == "true":
        commands += f"set service nat cgnat policy AUTO44_CP{number} select event session all-subscribers\n"
        commands += f"set service nat cgnat policy AUTO44_CP{number} select event session creation\n"
        commands += f"set service nat cgnat policy AUTO44_CP{number} select event session deletion\n"

    return commands


def generate_cgnat44_passthrough_config_commands(config, section):
    commands = ""
    number = section.split('_')[-1]
    ip_count = compute_ip_diff(config.get(section, 'ue-ip-start-ipv4'), config.get(section, 'ue-ip-end-ipv4'))
    #check for same start and end ip
    if ip_count > 1:
        commands += f"set resources group address-group AUTO44_PASS_AG{number} address-range {config.get(section, 'ue-ip-start-ipv4')} to {config.get(section, 'ue-ip-end-ipv4')}\n"
    else:
        commands += f"set resources group address-group AUTO44_PASS_AG{number} address {config.get(section, 'ue-ip-start-ipv4')}\n"

    commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} match source address-group AUTO44_PASS_AG{number}\n"
    global CGNAT_PRIORITY
    commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} priority {CGNAT_PRIORITY}\n"
    CGNAT_PRIORITY += 10
    commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} passthrough\n"
    commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} type 44\n"
    commands += f"set service nat cgnat interface {config.get(section,'policy-interface')} policy AUTO44_PASS_CP{number}\n"
    if config.get(section, 'logging').lower() == "true":
        commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} select event session all-subscribers\n"
        commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} select event session creation\n"
        commands += f"set service nat cgnat policy AUTO44_PASS_CP{number} select event session deletion\n"

    return commands


def generate_cgnat64_config_commands(config, section):
    commands = ""
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} address-allocation round-robin\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} address-pooling paired\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} entry A ip-address range start {config.get(section, 'pool-ip-start-ipv4')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} entry A ip-address range end {config.get(section, 'pool-ip-end-ipv4')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port allocation sequential\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port dynamic-block-allocation block-size 64\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port dynamic-block-allocation max-blocks-per-subscriber 8\n"
    if config.get(section, 'port-overloading').lower() == "true":
        commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port overloading enable\n"
    else:
        commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port overloading disable\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port range end {config.get(section, 'pool-port-end')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} port range start {config.get(section, 'pool-port-start')}\n"
    commands += f"set service nat pool AUTO_{config.get(section, 'pool-name')} type CGNAT\n"
    number = section.split('_')[-1]
    commands += f"set resources group address-group AUTO64_DAG{number} address '64:ff9b::/96'\n"
    ip_count = compute_ip_diff(config.get(section, 'ue-ip-start-ipv6'), config.get(section, 'ue-ip-end-ipv6'))
    #check for same start and end ip
    if ip_count > 1:
        commands += f"set resources group address-group AUTO64_SAG{number} address-range {config.get(section, 'ue-ip-start-ipv6')} to {config.get(section, 'ue-ip-end-ipv6')}\n"
    else:
        commands += f"set resources group address-group AUTO64_SAG{number} address {config.get(section, 'ue-ip-start-ipv6')}\n"

    commands += f"set service nat cgnat policy AUTO64_CP{number} match destination address-group AUTO64_DAG{number}\n"
    commands += f"set service nat cgnat policy AUTO64_CP{number} match source address-group AUTO64_SAG{number}\n"
    global CGNAT_PRIORITY
    commands += f"set service nat cgnat policy AUTO64_CP{number} priority {CGNAT_PRIORITY}\n"
    CGNAT_PRIORITY += 10
    commands += f"set service nat cgnat policy AUTO64_CP{number} translation destination mapping rfc6052 prefix-length 96\n"
    commands += f"set service nat cgnat policy AUTO64_CP{number} translation source mapping pool AUTO_{config.get(section, 'pool-name')}\n"
    commands += f"set service nat cgnat policy AUTO64_CP{number} type 64\n"
    commands += f"set service nat cgnat interface {config.get(section, 'policy-interface')} policy AUTO64_CP{number}\n"
    if config.get(section, 'logging').lower() == "true":
        commands += f"set service nat cgnat policy AUTO64_CP{number} select event session all-subscribers\n"
        commands += f"set service nat cgnat policy AUTO64_CP{number} select event session creation\n"
        commands += f"set service nat cgnat policy AUTO64_CP{number} select event session deletion\n"
    return commands


def generate_cgnat64_passthrough_config_commands(config, section):
    commands = ""
    number = section.split('_')[-1]
    commands += f"set resources group address-group AUTO64_PASS_DAG{number} address '::/0'\n"
    ip_count = compute_ip_diff(config.get(section, 'ue-ip-start-ipv6'), config.get(section, 'ue-ip-end-ipv6'))
    #check for same start and end ip
    if ip_count > 1:
        commands += f"set resources group address-group AUTO64_PASS_SAG{number} address-range {config.get(section, 'ue-ip-start-ipv6')} to {config.get(section, 'ue-ip-end-ipv6')}\n"
    else:
        commands += f"set resources group address-group AUTO64_PASS_SAG{number} address {config.get(section, 'ue-ip-start-ipv6')}\n"

    commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} match destination address-group AUTO64_PASS_DAG{number}\n"
    commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} match source address-group AUTO64_PASS_SAG{number}\n"
    global CGNAT_PRIORITY
    commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} priority {CGNAT_PRIORITY}\n"
    CGNAT_PRIORITY += 10
    commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} passthrough\n"
    commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} type 64\n"
    commands += f"set service nat cgnat interface {config.get(section, 'policy-interface')} policy AUTO64_PASS_CP{number}\n"
    if config.get(section, 'logging').lower() == "true":
        commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} select event session all-subscribers\n"
        commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} select event session creation\n"
        commands += f"set service nat cgnat policy AUTO64_PASS_CP{number} select event session deletion\n"
    return commands


def generate_dpi_config_commands(config, section):
    commands = ""
    #cpms config
    commands += f"set service telecom cpms 1 address {config.get(section, 'cpms-ipv4')}\n"
    commands += f"set service telecom cpms 1 password {config.get(section, 'cpms_passwd')}\n"
    commands += f"set service telecom cpms 1 port 8093\n"
    commands += f"set service telecom cpms 1 region_code {config.get(section, 'cpms_region_code')}\n"
    commands += f"set service telecom cpms 1 reported-name {config.get(section, 'dpi_reported_name')}\n"
    commands += f"set service telecom cpms 1 username {config.get(section, 'cpms_username')}\n"

    #pgw config
    pgw_interfaces = []
    pgw_mgmt_ips = []

    for key in config.options(section):
        if key.startswith("pgw-dpi-interface_"):
            match = re.search(r"pgw-dpi-interface_(\d+)$", key)
            if match:
                pgw_interfaces.append((int(match.group(1)), config.get(section, key)))
        elif key.endswith("_pgw-mgmt-ipv4"):
            match = re.search(r"^(\d+)_pgw-mgmt-ipv4$", key)
            if match:
                pgw_mgmt_ips.append((int(match.group(1)), config.get(section, key)))

    pgw_interfaces.sort(key=lambda item: item[0])
    pgw_mgmt_ips.sort(key=lambda item: item[0])

    for _, interface in pgw_interfaces:
        commands += f"set service telecom pgw interface {interface}\n"

    for pgw_id, mgmt_ip in pgw_mgmt_ips:
        commands += f"set service telecom pgw id {pgw_id} address {mgmt_ip}\n"
        commands += f"set service telecom pgw id {pgw_id} port 5555\n"
        commands += f"set service telecom pgw id {pgw_id} cpu-affinity 0-2\n"

    commands += f"set service telecom local notif-server address ipv4 {config.get('default', 'mgmt-ipv4')}\n"
    commands += f"set service telecom local notif-server port 5556\n"

    # hhe config
    if config.has_option(section,'enrich_enable'):
        commands += f"set service telecom enrichment enable {config.get(section,'enrich_enable')}\n"
        commands += f"set service telecom enrichment service address 127.0.0.1\n"
        commands += "set service telecom enrichment enrich implicit\n"
        if config.has_option(section,'enrich_default_profile'):
            commands += f"set service telecom enrichment default-profile {config.get(section,'enrich_default_profile')}\n"
        if config.has_option('fast_path_if_3','if_name'):
            commands += f"set service telecom enrichment service downlink-interface {config.get('fast_path_if_3','if_name')}\n"
        if config.has_option(section,'enrich_downlink_pbr_table'):
            commands += f"set service telecom enrichment service downlink-pbr-table {config.get(section,'enrich_downlink_pbr_table')}\n"
        if config.has_option('fast_path_if_2','if_name'):
            commands += f"set service telecom enrichment service pdn-interface {config.get('fast_path_if_2','if_name')}.{config.get('fast_path_if_2','vlan_id')}\n"
        if config.has_option('fast_path_if_3','if_name'):
            commands += f"set service telecom enrichment service uplink-interface {config.get('fast_path_if_3','if_name')}\n"
        if config.has_option(section,'enrich_uplink_pbr_table'):
            commands += f"set service telecom enrichment service uplink-pbr-table {config.get(section,'enrich_uplink_pbr_table')}\n"


    return commands


def generate_firewall_default_commands(config, section):
    commands = ""
    # static configuration.
    commands += "set security firewall name AUTO_ALLOW_ALL default-action drop\n"
    commands += "set security firewall name AUTO_ALLOW_ALL rule 1 icmpv6 name neighbor-advertisement\n"
    commands += "set security firewall name AUTO_ALLOW_ALL rule 1 action accept\n"
    commands += "set security firewall name AUTO_ALLOW_ALL rule 2 icmpv6 name neighbor-solicitation\n"
    commands += "set security firewall name AUTO_ALLOW_ALL rule 2 action accept\n"
    commands += "set security firewall name AUTO_ALLOW_ALL rule 3 action accept\n"

    commands += "set security firewall name AUTO_ALLOW_ONLY_IPV4 default-action drop\n"
    commands += "set security firewall name AUTO_ALLOW_ONLY_IPV4 rule 1 protocol ip\n"
    commands += "set security firewall name AUTO_ALLOW_ONLY_IPV4 rule 1 action accept\n"

    commands += "set security firewall name AUTO_DROP_ALL default-action drop\n"
    commands += "set security firewall name AUTO_DROP_ALL rule 100 action drop\n"

    commands += "set security firewall name AUTO_SESSION_ALLOW default-action drop\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 1 icmpv6 name neighbor-advertisement\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 1 action accept\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 2 icmpv6 name neighbor-solicitation\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 2 action accept\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 10 action accept\n"
    commands += "set security firewall name AUTO_SESSION_ALLOW rule 10 state enable\n"

    commands += "set security firewall name AUTO_SUGGESTED default-action drop\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 1 protocol tcp\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 1 state enable\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 1 action accept\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 2 protocol udp\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 2 state enable\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 2 action accept\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 3 protocol icmp\n"
    commands += "set security firewall name AUTO_SUGGESTED rule  3 state enable\n"
    commands += "set security firewall name AUTO_SUGGESTED rule 3 action accept\n"

    commands += "set security firewall name AUTO_ORIGINATE default-action drop\n"

    commands += "set security firewall name AUTO_LOCAL default-action drop\n"
    commands += "set security firewall name AUTO_LOCAL rule 1 police ratelimit 1\n"
    commands += "set security firewall name AUTO_LOCAL rule 1 police then action drop\n"
    commands += "set security firewall name AUTO_LOCAL rule 1 protocol icmp\n"
    commands += "set security firewall name AUTO_LOCAL rule 1 action accept\n"
    commands += "set security firewall name AUTO_LOCAL rule 2 state enable\n"
    commands += "set security firewall name AUTO_LOCAL rule 2 action accept\n"
    return commands


def generate_firewall_test_default_commands(config, section):
    commands = ""
    commands += "set security firewall name TEST default-action drop\n"
    commands += "set security firewall name TEST rule 1 action accept\n"
    commands += "set security firewall name TEST rule 1 protocol tcp\n"
    commands += "set security firewall name TEST rule 1 state enable\n"
    commands += "set security firewall name TEST rule 2 action accept\n"
    commands += "set security firewall name TEST rule 2 protocol icmp\n"
    commands += "set security firewall name TEST rule 2 state enable\n"
    commands += "set security firewall name TEST rule 3 action accept\n"
    commands += "set security firewall name TEST rule 3 protocol udp\n"
    commands += "set security firewall name TEST rule 3 state enable\n"
    commands += "set security firewall name TEST rule 4 action accept\n"
    commands += "set security firewall name TEST rule 4 icmpv6 name neighbor-advertisement\n"
    commands += "set security firewall name TEST rule 5 action accept\n"
    commands += "set security firewall name TEST rule 5 icmpv6 name echo-reply\n"
    commands += "set security firewall name TEST rule 6 action accept\n"
    commands += "set security firewall name TEST rule 6 icmpv6 name echo-reply\n"
    commands += "set security firewall name TEST rule 7 action accept\n"
    commands += "set security firewall name TEST rule 7 icmpv6 name echo-request\n"
    commands += "set security firewall name TEST rule 8 action accept\n"
    commands += "set security firewall name TEST rule 8 icmpv6 name neighbor-solicitation\n"
    return commands

def generate_firewall_ruleset_commands(config, section):
    commands = ""
    ruleset_name = config.get(section, 'ruleset-name')
    rule_number = config.get(section, 'rule-number')
    action = config.get(section, 'action')

    commands += f"set security firewall name {ruleset_name} default-action drop\n"
    commands += f"set security firewall name {ruleset_name} rule {rule_number} action {action}\n"

    if config.has_option(section, 'src-ipv4'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} source address {config.get(section, 'src-ipv4')}\n"
    if config.has_option(section, 'src-ipv6'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} source address {config.get(section, 'src-ipv6')}\n"

    if config.has_option(section, 'dst-ipv4'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} destination address {config.get(section, 'dst-ipv4')}\n"
    if config.has_option(section, 'dst-ipv6'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} destination address {config.get(section, 'dst-ipv6')}\n"
    if config.has_option(section, 'src-port'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} source port {config.get(section, 'src-port')}\n"
    if config.has_option(section, 'dst-port'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} destination port {config.get(section, 'dst-port')}\n"
    if config.has_option(section, 'protocol'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} protocol {config.get(section, 'protocol')}\n"
    if config.has_option(section, 'state'):
        commands += f"set security firewall name {ruleset_name} rule {rule_number} state {config.get(section, 'state')}\n"

    return commands

def generate_fw_attached_to_interface_commands(config, section):
    commands = ""

    # Check if VLAN is set
    if config.has_option(section, 'vlan'):
        # VLAN is present, include it in the command
        commands += f"set interfaces dataplane {config.get(section,'interface-name')} vif {config.get(section,'vlan')} firewall {config.get(section,'direction')} {config.get(section,'fw-name')}\n"
    else:
        # VLAN is not present, omit the VLAN from the command
        commands += f"set interfaces dataplane {config.get(section,'interface-name')} firewall {config.get(section,'direction')} {config.get(section,'fw-name')}\n"

    return commands

def generate_zone_creation_commands(config, section):
    commands = ""
    zone_name = config.get(section, 'zone-name')
    zone_interface = config.get(section, 'zone-interface')
    
    commands += f"set security zone-policy zone {zone_name} interface {zone_interface}\n"
    return commands


def generate_local_zone_creation_commands(config, section):
    commands = ""
    local_zone_name = config.get(section, 'local-zone-name')
    commands += f"set security zone-policy zone {local_zone_name} local-zone\n"
    return commands


def generate_zone_communication_commands(config, section):
    commands = ""
    from_zone = config.get(section, 'from-zone')
    to_zone = config.get(section, 'to-zone')
    fwruleset = config.get(section, 'fwruleset')

    commands += f"set security zone-policy zone {from_zone} to {to_zone} firewall {fwruleset}\n"
    return commands

def generate_secgw_ha_commands(config, section):
    enb_subif = 'dp0s20' + '.' + config.get(section,'enb-vlan')
    mme_subif = 'dp0s21' + '.' + config.get(section,'mme-vlan')
    sync_subif = 'eth3' + '.' + config.get(section,'sync-vlan')

    commands = ""

    commands += f"set interfaces dataplane dp0s20 vif {config.get(section,'enb-vlan')} vrrp vrrp-group {config.get(section,'enb-vrrp-group')} sync-group {config.get(section,'sync-group')}\n"
    commands += f"set interfaces dataplane dp0s20 vif {config.get(section,'enb-vlan')} vrrp vrrp-group {config.get(section,'enb-vrrp-group')} virtual-address {config.get(section,'enb-ipv4')}\n"

    commands += f"set interfaces dataplane dp0s21 vif {config.get(section,'mme-vlan')} vrrp vrrp-group {config.get(section,'mme-vrrp-group')} sync-group {config.get(section,'sync-group')}\n"
    commands += f"set interfaces dataplane dp0s21 vif {config.get(section,'mme-vlan')} vrrp vrrp-group {config.get(section,'mme-vrrp-group')} virtual-address {config.get(section,'mme-ipv4')}\n"
    commands += f"set interfaces dataplane dp0s21 vif {config.get(section,'mme-vlan')} vrrp vrrp-group {config.get(section,'mme-vrrp-group')} notify system\n"

    commands += f"set interfaces system eth3 vif {config.get(section,'sync-vlan')}\n"

    commands += f"set interfaces system {config.get('default','management-int-name')} vrrp vrrp-group {config.get(section,'management-vrrp-group')} sync-group {config.get(section,'sync-group')}\n"
    commands += f"set interfaces system {config.get('default','management-int-name')} vrrp vrrp-group {config.get(section,'management-vrrp-group')} virtual-address {config.get('default','mgmt-ipv4')}\n"

    commands +="set security vpn ha enable\n"

    commands += f"set system ha parameters local-ip {config.get(section,'local-ipv4')}\n"
    commands += f"set system ha parameters remote-ip {config.get(section,'remote-ipv4')}\n"
    commands += f"set system ha parameters internal-ip {enb_subif} address {config.get(section,'internal-enb-if-ipv4')}\n"
    commands += f"set system ha parameters internal-ip {mme_subif} address {config.get(section,'internal-mme-if-ipv4')}\n"
    commands += f"set system ha parameters internal-ip {sync_subif} address {config.get(section,'internal-sync-if-ipv4')}\n"
    commands += f"set system ha parameters internal-ip {config.get('default','management-int-name')} address {config.get(section,'internal-mgmt-if-ipv4')}\n"
    commands += f"set system ha state enable\n"

    return commands

def generate_cips_config_commands(config, section):
    disable_rule_id = [
        2210044, 1000030, 2210026, 2200038, 2260001, 2200075, 2200070, 2210045, 2200074, 2210035, 2210016, 2210033, 2210054, 2210036,
        2210046, 2210042, 2210032, 2200036, 2260000, 2224005, 2210029, 2210020, 2210000, 2210038, 2210027, 2221010, 2200035 
    ]

    commands = ""
    #default app layer configuration
    commands += "set idp app-layer-protocols dcerpc mode detect-and-parse\n"
    commands += "set idp app-layer-protocols dhcp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols dnp3 mode detect-and-parse\n"
    commands += "set idp app-layer-protocols dns mode detect-and-parse\n"
    commands += "set idp app-layer-protocols enip mode detect-and-parse\n"
    commands += "set idp app-layer-protocols ftp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols http mode detect-and-parse\n"
    commands += "set idp app-layer-protocols http2 mode disable\n"
    commands += "set idp app-layer-protocols ike mode detect-and-parse\n"
    commands += "set idp app-layer-protocols imap mode detect-and-parse\n"
    commands += "set idp app-layer-protocols krb5 mode detect-and-parse\n"
    commands += "set idp app-layer-protocols modbus mode detect-and-parse\n"
    commands += "set idp app-layer-protocols mqtt mode detect-and-parse\n"
    commands += "set idp app-layer-protocols nfs mode detect-and-parse\n"
    commands += "set idp app-layer-protocols ntp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols rdp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols rfb mode detect-and-parse\n"
    commands += "set idp app-layer-protocols sip mode detect-and-parse\n"
    commands += "set idp app-layer-protocols smb mode detect-and-parse\n"
    commands += "set idp app-layer-protocols snmp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols ssh mode detect-and-parse\n"
    commands += "set idp app-layer-protocols tftp mode detect-and-parse\n"
    commands += "set idp app-layer-protocols tls mode detect-and-parse\n"
    commands += "set idp app-layer-protocols tls encryption-handling bypass\n"

    #disable rule id's commands
    for rule_id in disable_rule_id:
        commands += f"set idp rule disable rule-id {rule_id}\n"

    #capture mode configuration
    commands += f"set idp capture-mode dpdk dpdk-config dpdk-interface-whitelist {config.get(section, 'whitelist-interface1')}\n"
    commands += f"set idp capture-mode dpdk dpdk-config dpdk-interface-whitelist {config.get(section, 'whitelist-interface2')}\n"
    commands += "set idp capture-mode dpdk interface eth1 copy-interface eth2\n"
    commands += "set idp capture-mode dpdk interface eth1 rx-checksum rx-offload true\n"
    commands += "set idp capture-mode dpdk interface eth2 copy-interface eth1\n"
    commands += "set idp capture-mode dpdk interface eth2 rx-checksum rx-offload true\n"
    commands += "set idp capture-mode dpdk mode ips\n"
    commands += "set idp capture-mode dpdk interface-default-config rx-desc 2048\n"
    commands += "set idp capture-mode dpdk interface-default-config tx-desc 4096\n"

    #cips logging configurations
    if config.get(section, 'logging') == "true":
        commands += "set idp logging eve types alerts\n"
        # DO NOT enable alerts as we are not consuming them as of now
        #commands += "set idp logging eve types dcerpc enable\n"
        #commands += "set idp logging eve types dhcp\n"
        #commands += "set idp logging eve types dnp3 enable\n"
        #commands += "set idp logging eve types dns\n"
        #commands += "set idp logging eve types files\n"
        #commands += "set idp logging eve types flow status enable\n"
        #commands += "set idp logging eve types ftp enable\n"
        #commands += "set idp logging eve types http\n"
        #commands += "set idp logging eve types ikev2 enable\n"
        #commands += "set idp logging eve types krb5 enable\n"
        #commands += "set idp logging eve types nfs enable\n"
        #commands += "set idp logging eve types rdp enable\n"
        #commands += "set idp logging eve types rfb enable\n"
        #commands += "set idp logging eve types sip enable\n"
        #commands += "set idp logging eve types smb enable\n"
        #commands += "set idp logging eve types smtp\n"
        #commands += "set idp logging eve types snmp enable\n"
        #commands += "set idp logging eve types ssh enable\n"
        #commands += "set idp logging eve types tftp enable\n"
        #commands += "set idp logging eve types tls\n"

    #CIPS Policy Configuration
    commands += "set idp policy enable-all\n"

    #CIPS Rule-Vars Configuration
    commands += f"set idp rule-vars address HOME_NET val {config.get(section, 'protected-network-ipv4')}\n"

    #CIPS Signature Configuration
    commands += f"set idp signature add-source {config.get(section, 'src-name')} url {config.get(section, 'src-url')}\n"

    #fsetting low manager 1 for any cpu-count
    commands += "set system boot-loader default-smp-affinity 0\n"

    #setting cpu affinities and rx queues base on no. of cpu's
    if config.get(section, 'cpu-count') == "4":
        commands += "set idp advanced-tuning cpu-affinity management-cpu-set 1\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 2\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 3\n"
        commands += "set idp advanced-tuning flow managers 1\n"
        commands += "set idp capture-mode dpdk interface eth1 rx-queues 1\n"
        commands += "set idp capture-mode dpdk interface eth2 rx-queues 1\n"
        commands += "set system boot-loader isolated-cpus 2-3\n"

    elif config.get(section, 'cpu-count') == "6":
        commands += "set idp advanced-tuning cpu-affinity management-cpu-set 1\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 2\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 3\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 4\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 5\n"
        commands += "set idp advanced-tuning flow managers 1\n"
        commands += "set idp capture-mode dpdk interface eth1 rx-queues 2\n"
        commands += "set idp capture-mode dpdk interface eth2 rx-queues 2\n"
        commands += "set system boot-loader isolated-cpus 2-5\n"

    elif config.get(section, 'cpu-count') == "8":
        commands += "set idp advanced-tuning cpu-affinity management-cpu-set 1\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 2\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 3\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 4\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 5\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 6\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 7\n"
        commands += "set idp advanced-tuning flow managers 1\n"
        commands += "set idp capture-mode dpdk interface eth1 rx-queues 3\n"
        commands += "set idp capture-mode dpdk interface eth2 rx-queues 3\n"
        commands += "set system boot-loader isolated-cpus 2-7\n"

    elif config.get(section, 'cpu-count') == "10":
        commands += "set idp advanced-tuning cpu-affinity management-cpu-set 1\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 2\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 3\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 4\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 5\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 6\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 7\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 8\n"
        commands += "set idp advanced-tuning cpu-affinity worker-cpu-set 9\n"
        commands += "set idp advanced-tuning flow managers 1\n"
        commands += "set idp capture-mode dpdk interface eth1 rx-queues 4\n"
        commands += "set idp capture-mode dpdk interface eth2 rx-queues 4\n"
        commands += "set system boot-loader isolated-cpus 2-9\n"

    #conf for main dc
    if config.get(section, 'deployment') == "main":
        commands += "set idp advanced-tuning flow hash-size 100000\n"
        commands += "set idp advanced-tuning flow memcap unit gb\n"
        commands += "set idp advanced-tuning flow memcap value 8\n"
        commands += "set idp advanced-tuning flow prealloc 100000\n"
        commands += "set idp advanced-tuning host memcap unit gb\n"
        commands += "set idp advanced-tuning host memcap value 2\n"
        commands += "set idp advanced-tuning host prealloc 100000\n"
        commands += "set idp advanced-tuning stream memcap unit gb\n"
        commands += "set idp advanced-tuning stream memcap value 5\n"
        commands += "set idp advanced-tuning stream prealloc-sessions 100000\n"
        commands += "set idp advanced-tuning stream reassembly memcap unit gb\n"
        commands += "set idp advanced-tuning stream reassembly memcap value 8\n"
        commands += "set idp advanced-tuning stream reassembly segment-prealloc 100000\n"
        commands += "set idp app-layer-protocols http memcap unit gb\n"
        commands += "set idp app-layer-protocols http memcap value 8\n"

    #conf for mini dc
    elif config.get(section, 'deployment') == "mini":
        commands += "set idp advanced-tuning flow hash-size 8000000\n"
        commands += "set idp advanced-tuning flow memcap unit gb\n"
        commands += "set idp advanced-tuning flow memcap value 45\n"
        commands += "set idp advanced-tuning flow prealloc 2000000\n"
        commands += "set idp advanced-tuning host memcap unit gb\n"
        commands += "set idp advanced-tuning host memcap value 10\n"
        commands += "set idp advanced-tuning host prealloc 2000000\n"
        commands += "set idp advanced-tuning stream memcap unit gb\n"
        commands += "set idp advanced-tuning stream memcap value 30\n"
        commands += "set idp advanced-tuning stream prealloc-sessions 1000000\n"
        commands += "set idp advanced-tuning stream reassembly memcap unit gb\n"
        commands += "set idp advanced-tuning stream reassembly memcap value 60\n"
        commands += "set idp advanced-tuning stream reassembly segment-prealloc 1000000\n"
        commands += "set idp app-layer-protocols http memcap unit gb\n"
        commands += "set idp app-layer-protocols http memcap value 45\n"

    #advance tuning commands common for both
    commands += "set idp advanced-tuning stream bypass\n"
    commands += "set idp advanced-tuning stream memcap-policy bypass\n"
    commands += "set idp advanced-tuning stream reassembly memcap-policy bypass\n"
    commands += "set idp advanced-tuning stream checksum-validation disable\n"
    commands += "set idp advanced-tuning stream disable-drop-invalid\n"
    commands += "set idp advanced-tuning stream reassembly depth value 2\n"
    commands += "set idp advanced-tuning stream reassembly depth unit kb\n"

    return commands

    
def update_cips_signature_command(config, section):
    commands = ""
    commands += "run restart idp forced\n"
    commands += "sleep 60\n"
    commands += "run update idp signatures force quiet\n"
    return commands

def generate_imsdp_commands(config, section):
    ctrl_ipv4 = config.get("default", "ctrl-ipv4")
    ctrl_ipv4_only = ctrl_ipv4.split("/")[0]
    commands = ""
    commands += f"set service imsdp data-plane listen-address {ctrl_ipv4_only} \n"
    commands += (
        f"set service imsdp data-plane num-pods {config.get(section,'num-pods')}\n"
    )
    commands += f"set service imsdp data-plane max-bw {config.get(section,'max-bandwidth')} \n"
    commands += f"set service imsdp data-plane max-fp {config.get(section,'max-flowpair')} \n"
    # kpi-reset interval
    commands += f"set service imsdp data-plane kpi-reset-interval 30\n"
    if config.has_option("host_firewall", "imscp-sync-port"):
        commands += f"set service imsdp data-plane sync-port {config.get('host_firewall','imscp-sync-port')} \n"
    else:
        commands += "set service imsdp data-plane sync-port 12000 \n"

    if config.has_option("host_firewall", "imscp-ind-port"):
        commands += f"set service imsdp data-plane indi-port {config.get('host_firewall','imscp-ind-port')} \n"
    else:
        commands += "set service imsdp data-plane indi-port 12010 \n"

    if config.has_option(section, "transcoder-cp-ipv4"):
        commands += f"set service imsdp transcoder address {config.get(section,'transcoder-cp-ipv4')}\n"
        if config.has_option("host_firewall", "transcoder-api-port"):
            commands += f"set service imsdp transcoder port {config.get('host_firewall','transcoder-api-port')} \n"
        else:
            commands += "set service imsdp transcoder port 15000\n"

        if config.has_option("host_firewall", "transcoder-notif-port"):
            commands += f"set service imsdp transcoder notif-port {config.get('host_firewall','transcoder-notif-port')} \n"
        else:
            commands += "set service imsdp transcoder notif-port 15001\n"

    return commands

def generate_imsdp_pod_config_commands(config, section):
    commands = ""
    number = section.split('_')[-1]
    if compute_ip_diff({config.get(section,'media-start-ipv4')},{config.get(section,'media-end-ipv4')}) == 2:
       commands += f"set resources group address-group ag{number} address-range {config.get(section,'media-start-ipv4')} to {config.get(section,'media-end-ipv4')}\n"
    else:
       commands += f"set resources group address-group ag{number} address {config.get(section,'media-start-ipv4')}\n"
    commands += f"set service imsdp pod {number} address-group ag{number}\n"
    commands += f"set service imsdp pod {number} max-media-port {config.get(section,'media-end-port')}\n"
    commands += f"set service imsdp pod {number} min-media-port {config.get(section,'media-start-port')}\n"

    return commands

################################################################################
# Linux firewalling commands for all the nodes                                 #
################################################################################
def generate_host_firewall_commands(config, section):
    global HOSTFW_RULE_NUMBER_MGMT
    global HOSTFW_RULE_NUMBER_CTRL
    node_name = config.get("default", 'node-name')
    commands = ""
    rule_no = 1
    ctrl_rule_no = 1
    if config.has_section("default") :
        #Accepting compute machine traffics.
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting compute machine traffics'\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(section,'compute-ip-ipv4')}\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
        rule_no+=1
        #Accepting controller machine requests on management interface.
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting controller machine requests on management interface'\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(section,'controller-ip-ipv4')}\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
        rule_no+=1
        #Allowing icmp from the range of ips 50 packets per second.
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Allowing icmp from the range of ips 50 packets per second'\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto icmp\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} rate-limit-per-second 50\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range start {config.get(section,'start-range-ssh-ipv4')}\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range end {config.get(section,'end-range-ssh-ipv4')}\n"
        rule_no+=1

        for config_sec in config.sections():
            #Limiting Number of concurrent conection to the management interface from particualr range of IPs.
            if config_sec.startswith("ssh") :
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Limiting Number of concurrent conection to the management interface from particualr range of IPs'\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} concurrent-connections {config.get(section,'conn-connection-no')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport {config.get(config_sec,'port')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action DROP\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range start {config.get(section,'start-range-ssh-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range end {config.get(section,'end-range-ssh-ipv4')}\n"
                rule_no+=1
                #Accepting ssh connection from range of IPs
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting ssh connection from range of IPs'\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport {config.get(config_sec,'port')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range start {config.get(section,'start-range-ssh-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range end {config.get(section,'end-range-ssh-ipv4')}\n"
                rule_no+=1
                #Accepting scp from the local machines(ip range given)
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting scp from the local machines(ip range given)'\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport {config.get(config_sec,'local-usr-ssh-port')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range start {config.get(section,'start-range-ssh-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address range end {config.get(section,'end-range-ssh-ipv4')}\n"
                rule_no+=1

            if node_name == "cips":
                #Accepting the signature vm's tcp traffic.
                if config_sec.startswith("cips_") :
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting the signature vms tcp traffic'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'cips-signature-vm-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    rule_no+=1
                #Accepting ha-mon traffic.
                if config_sec.startswith("hamon_reporter"):
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting ha-mon traffic'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'dpi-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 5566\n"
                    rule_no+=1

            if node_name == "firewall":
                #Accepting ha-mon traffic.
                if config_sec.startswith("hamon_reporter"):
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting ha-mon traffic'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'dpi-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 5566\n"
                    rule_no+=1

            if node_name == "dpi":
                #Accepting traffics from the ha-mon reporter.
                if config_sec.startswith("dpi_") :
                    #cgnat
                    if config.has_option(config_sec, "cgnat-management-ipv4"):
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting traffics from the ha-mon reporter for cgnat'\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'cgnat-management-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport 5566\n"
                        rule_no+=1
                    #cips
                    if config.has_option(config_sec, "cips-management-ipv4"):
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting traffics from the ha-mon reporter for cips'\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'cips-management-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport 5566\n"
                        rule_no+=1
                    # #secgw
                    # if config.has_option(config_sec, "enrich_service_address-ipv4"):
                    #   commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(section,'secgw-management')}\n"
                    #   commands += f"sset interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    #   commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    #   commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport 5566\n"
                    #   rule_no+=1
                    #firewall
                    if config.has_option(config_sec, "firewall-management-ipv4"):
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting traffics from the ha-mon reporter for firewall'\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'firewall-management-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport 5566\n"
                        rule_no+=1
                    #hhe node
                    if config.has_option(config_sec, "enrich_service_address-ipv4"):
                        #port port1
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'enrich_service_address-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 8001\n"
                        rule_no+=1
                        # port port2
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'enrich_service_address-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 8002\n"
                        rule_no+=1

                        # port port3
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'enrich_service_address-ipv4')}\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 10010\n"
                        rule_no+=1


                    #cpms gui
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting TAC+ messages on management interface'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'cpms-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 8093\n"
                    rule_no+=1

            if node_name == "cgnat":
                #Accepting ha-mon traffic.
                if config_sec.startswith("hamon_reporter"):
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting ha-mon traffic'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get(config_sec,'dpi-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} sport 5566\n"
                    rule_no+=1

        if node_name == "secgw":
            #Accepting peer sync interface traffic.
            if config.has_section("ssh") and config.has_section("secgw-ha"):
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting peer sync interface traffic'\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get('secgw-ha','remote-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto tcp\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dport {config.get('ssh','port')}\n"
                rule_no+=1
	        #Accepting mgmnt vrrp ip traffic.
            if config.has_option('snmp','peer-ipv4'):
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting mgmnt vrrp ip traffic'\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get('snmp','peer-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dst-address prefix 224.0.0.18\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} proto vrrp\n"
                commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                rule_no+=1
        if node_name == "imsdp" or node_name == "ibcfdp":
            ctrl_rule_no = 1
            ctrl_ipv4 = config.get("default", "ctrl-ipv4")
            ctrl_ipv4_only = ctrl_ipv4.split("/")[0]
            # Accepting CP connection & Indication port
            for key in config.options(
                "imsdp"
            ):  # Get all keys under the section 'imsdp'
                if key.startswith("imscp-worker-ip_") and key.endswith("-ipv4"):
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting CP connection & Indication port'\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto tcp\n"
                    if config.has_option(section, "ind-port"):
                        commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dport {config.get(section,'ind-port')}\n"
                    else:
                        commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dport 12010\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp', key)}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                    ctrl_rule_no += 1
                    # Accepting CP connection & Sync port
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting CP connection & Sync port'\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto tcp\n"
                    if config.has_option(section, "ind-port"):
                        commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dport {config.get(section,'sync-port')}\n"
                    else:
                        commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dport 12000\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp', key)}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                    ctrl_rule_no += 1
                    # Accepting icmp pkt from cp worker
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting icmp pkt cp worker'\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto icmp\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp', key)}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                    ctrl_rule_no += 1
                # Accepting LI connection
                if key.startswith("li-server-ip_") and key.endswith("-ipv4"):
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} description 'Accepting LI connection'\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} src-address prefix {config.get('imsdp', key)}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} dst-address prefix {config.get('default','mgmt-ipv4')}\n"
                    commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {rule_no} action ACCEPT\n"
                    rule_no += 1
            # Accepting TR connection & Api port
            if config.has_option("imsdp", "transcoder-cp-ipv4"):
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting TR connection & Api port'\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto tcp\n"
                if config.has_option(section, "transcoder-api-port"):
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {rule_no} sport {config.get(section,'transcoder-api-port')}\n"
                else:
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} sport 15000\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp','transcoder-cp-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                ctrl_rule_no += 1
                # Accepting TR connection & Notif port
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting TR connection & Notif port'\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto tcp\n"
                if config.has_option(section, "transcoder-notif-port"):
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} sport {config.get(section,'transcoder-notif-port')}\n"
                else:
                    commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} sport 15001\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp','transcoder-cp-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                ctrl_rule_no += 1
                # Accepting icmp pkt from transcoder cp
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} description 'Accepting icmp pkt from transcoder cp'\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} proto icmp\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} src-address prefix {config.get('imsdp','transcoder-cp-ipv4')}\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} dst-address prefix {ctrl_ipv4_only}\n"
                commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {ctrl_rule_no} action ACCEPT\n"
                ctrl_rule_no += 1

            # Droping the default traffic destined towards the control ip.
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL + 400} description 'Droping the default traffic destined towards the control ip'\n"
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL + 400} dst-address prefix {ctrl_ipv4_only}\n"
            commands += f"set interfaces system {config.get('default','ctrl-interface-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL + 400} action DROP\n"

        #Droping the default traffic destined towards the management ip.
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT + 400} description 'Droping the default traffic destined towards the management ip'\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT + 400} dst-address prefix {config.get('default','mgmt-ipv4')}\n"
        commands += f"set interfaces system {config.get('default','management-int-name')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT + 400} action DROP\n"

        return commands

def generate_host_fw_whitelist_ipv4_commands(config,section):
    global HOSTFW_RULE_NUMBER_MGMT
    global HOSTFW_RULE_NUMBER_CTRL
    commands = ""
    if config.get(section,'interface') in ["ens3", "eth0"] or (config.get("default", "node-name") in ["cips", "firewall"] and config.get(section, "interface") == "eth0"):
        if config.has_option(section, 'src-address-ipv4'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} src-address prefix {config.get(section,'src-address-ipv4')}\n"
        if config.has_option(section, 'protocol'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} proto {config.get(section,'protocol')}\n"
        if config.has_option(section, 'action'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} action {config.get(section,'action')}\n"
        else:
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} action ACCEPT\n"
        if config.has_option(section, 'source-port'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} sport {config.get(section,'source-port')}\n"
        if config.has_option(section, 'destination-port'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} dport {config.get(section,'destination-port')}\n"
        if config.has_option(section, 'dst-address-ipv4'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} dst-address prefix {config.get(section,'dst-address-ipv4')}\n"
        if config.has_option(section, 'state'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} state {config.get(section,'state')} \n"
        if config.has_option(section, 'description'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_MGMT} description {config.get(section,'description')} \n"
        HOSTFW_RULE_NUMBER_MGMT+=1
    else:
        if config.has_option(section, 'src-address-ipv4'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} src-address prefix {config.get(section,'src-address-ipv4')}\n"
        if config.has_option(section, 'protocol'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} proto {config.get(section,'protocol')}\n"
        if config.has_option(section, 'action'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} action {config.get(section,'action')}\n"
        else:
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} action ACCEPT\n"
        if config.has_option(section, 'source-port'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} sport {config.get(section,'source-port')}\n"
        if config.has_option(section, 'destination-port'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} dport {config.get(section,'destination-port')}\n"
        if config.has_option(section, 'dst-address-ipv4'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} dst-address prefix {config.get(section,'dst-address-ipv4')}\n"
        if config.has_option(section, 'state'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} state {config.get(section,'state')} \n"
        if config.has_option(section, 'description'):
            commands += f"set interfaces system {config.get(section,'interface')} hostfw in match-rule {HOSTFW_RULE_NUMBER_CTRL} description {config.get(section,'description')} \n"
        HOSTFW_RULE_NUMBER_CTRL+=1

    return commands

def generate_epdg_ipsec_profile_config_commands(config, section):
    commands = ""
    if config.has_option(section, "auth-id"):
        commands += f"set security vpn ipsec epdg profile P1 authentication id {config.get(section,'auth-id')}\n"
    else:
        commands += f"set security vpn ipsec epdg profile P1 authentication id ims\n"
    commands += f"set security vpn ipsec epdg profile P1 authentication mode null\n"
    if config.has_option("default", "lo-ipv4"):
        only_loopback_ip = config.get("default", "lo-ipv4").split("/")[0]
        commands += f"set security vpn ipsec epdg profile P1 local-address {only_loopback_ip}\n"
    else:
        ip_only = config.get("fast_path_if_1", "if-ipv4").split("/")[0]
        commands += f"set security vpn ipsec epdg profile P1 local-address {ip_only}\n"    
    commands += f"set security vpn ipsec epdg profile P1 tunnel 1 local prefix {config.get(section,'tunnel-local-prefix-ipv4')}\n"
    commands += f"set security vpn ipsec epdg profile P1 tunnel 1 remote prefix {config.get(section,'tunnel-remote-prefix-ipv4')}\n"

    if (
        config.has_option("fast_path_if_1", "if-ipv6")
        and config.has_option(section, "tunnel-local-prefix-ipv6")
        and config.has_option(section, "tunnel-remote-prefix-ipv6")
    ):
        if config.has_option(section, "auth-id"):
            commands += f"set security vpn ipsec epdg profile P2 authentication id {config.get(section,'auth-id')}\n"
        else:
            commands += (
                f"set security vpn ipsec epdg profile P2 authentication id ims\n"
            )
        commands += f"set security vpn ipsec epdg profile P2 authentication mode null\n"
        ip6_local = config.get("fast_path_if_1", "if-ipv6")
        ip6_only = ip6_local.split("/")[0]
        commands += f"set security vpn ipsec epdg profile P2 local-address {ip6_only}\n"
        commands += f"set security vpn ipsec epdg profile P2 tunnel 1 local prefix {config.get(section,'tunnel-local-prefix-ipv6')}\n"
        commands += f"set security vpn ipsec epdg profile P2 tunnel 1 remote prefix {config.get(section,'tunnel-remote-prefix-ipv6')}\n"
    return commands


def generate_haf_mdp_commands(config, section):
    commands = ""
    commands += f"set service wigw haf dataplane mdp-nodes id {config.get(section,'id')} physical-ip address {config.get(section,'dp-ctrl-ipv4')}\n"
    return commands
    

def generate_epdg_config_commands(config, section):
    commands = ""
    commands += f"set service wigw epdg control-plane address {config.get(section,'epdgcp-ipv4')}\n"
    ctrl_ipv4 = config.get("default", "ctrl-ipv4")
    ctrl_ipv4_only = ctrl_ipv4.split("/")[0]
    commands += f"set service wigw epdg data-plane address {ctrl_ipv4_only}\n"
    if config.has_option(section, "gtp-port"):
        commands += f"set service wigw epdg data-plane gtp-port {config.get(section,'gtp-port')}\n"
    else:
        commands += f"set service wigw epdg data-plane gtp-port 5010\n"
    commands += f"set service wigw epdg data-plane id {config.get(section,'dp-id')}\n"
    if config.has_option(section, "ike-port"):
        commands += f"set service wigw epdg data-plane ike-port {config.get(section,'ike-port')}\n"
    else:
        commands += f"set service wigw epdg data-plane ike-port 4000\n"
    commands += f"set service wigw epdg enable\n"
    commands += f"set service wigw epdg dev-id-notif disabled\n"
    commands += f"set service wigw epdg swu-notif disabled\n"
    commands += f"set service wigw epdg ratelimit enabled\n"
    commands += f"set service wigw epdg ip-mode mode ipv4\n"
    commands += f"set service wigw epdg attach-on-attach disabled\n"
    commands += f"set service wigw epdg log all enabled\n"
    commands += f"set service wigw epdg db-store enabled\n"
    commands += f"set service wigw haf control-plane node_1-ip address {config.get(section,'epdgcp-node1-ipv4')}\n"
    commands += f"set service wigw haf control-plane node_2-ip address  {config.get(section,'epdgcp-node2-ipv4')}\n"
    if config.has_option("default", "ctrl-interface-name"):
        commands += f"set service wigw haf dataplane interface {config.get('default','ctrl-interface-name')}\n"
        commands += f"set protocols static route {config.get(section,'epdgcp-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')} interface {config.get('default','ctrl-interface-name')}\n"
        commands += f"set protocols static route {config.get(section,'epdgcp-node1-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')} interface {config.get('default','ctrl-interface-name')}\n"
        commands += f"set protocols static route {config.get(section,'epdgcp-node2-ipv4')}/32 next-hop {config.get('default','ctrl-gw-ipv4')} interface {config.get('default','ctrl-interface-name')}\n"
    else:
        commands += f"set service wigw haf dataplane interface {MGMT_IF_NAME}\n"
    if config.has_option("default", "ctrl-gw-ipv4"):
        commands += f"set service wigw haf router-address address {config.get('default','ctrl-gw-ipv4')}\n"
    else:
        commands += f"set service wigw haf router-address address {config.get('default','mgmt-gw-ipv4')}\n"
    commands += f"set service wigw haf dataplane physical-ip address {ctrl_ipv4_only}\n"
    commands += f"set service wigw haf trace-level enabled\n"
    commands += f"set service wigw epdg swu interface {config.get('fast_path_if_1','if_name')}.{config.get('fast_path_if_1','vlan_id')}\n"
    commands += f"set service wigw epdg s2b interface {config.get('fast_path_if_2','if_name')}.{config.get('fast_path_if_2','vlan_id')}\n"
    if config.has_option("default", "lo-ipv4"):
        commands += "set service wigw epdg lo interface lo1\n"
    commands += f"set service wigw epdg max-subscribers {config.get(section,'maximum-subscriber')}\n"
    commands += (
        f"set security vpn ike ikesa-limit {config.get(section,'maximum-subscriber')}\n"
    )
    load_balancer_ip = config.get('default','load-balancer-ipv4').split('/')[0]
    commands += f"set protocols static route 0.0.0.0/0 next-hop {load_balancer_ip} interface {config.get('fast_path_if_1','if_name')}.{config.get('fast_path_if_1','vlan_id')}\n"
    commands += f"set system default dataplane cpu-affinity 5-9\n"
    commands += f"set system default dataplane max-rx-queue 5\n"
    commands += f"set security ip-packet-filter group RL1 rule 10 action accept\n"
    commands += f"set security ip-packet-filter group RL1 rule 10 match destination port number 500\n"
    commands += f"set security ip-packet-filter group RL1 rule 10 match protocol base name udp\n"
    commands += f"set security ip-packet-filter group RL1 rule 10 police ratelimit 10pps\n"
    commands += f"set security ip-packet-filter group RL1 rule 10 police then action drop\n"
    commands += f"set security ip-packet-filter group RL1 ip-version ipv4\n"
    commands += f"set security ip-packet-filter interface {config.get('fast_path_if_1','if_name')}.{config.get('fast_path_if_1','vlan_id')} in RL1\n"
    commands += f"set system coredump process maximum-size 32G\n"
    commands += f"set system coredump storage compress yes\n"
    commands += f"set system coredump storage max-file-size 28G\n"
    commands += f"set system coredump storage mode external\n"
    commands += f"set system coredump storage total-size 120G\n"
    return commands

def generate_epdg_pcscf_imsdp_route_config_commands(config, section):
    commands = ""
    if section.startswith("epdg_pcscf_"):
        commands += f"set protocols static interface-route {config.get(section,'pcscf-subnet')} next-hop-interface gtptun\n"
    if section.startswith("epdg_imsdp_"):
        commands += f"set protocols static interface-route {config.get(section,'imsdp-subnet')} next-hop-interface gtptun\n"
    return commands

def generate_epdg_pgwdp_route_config_commands(config, section):
    commands = ""
    commands += f"set protocols static route {config.get(section,'pgwdp-subnet')} next-hop {config.get(section,'next-hop-ipv4')} interface {config.get('fast_path_if_2','if_name')}.{config.get('fast_path_if_2','vlan_id')}\n"
    return commands

def generate_lac_config_commands(config, section):
    commands = ""
    commands += f"set l2tp application parameter logging debug {config.get(section,'logging-debug')}\n"
    commands += f"set l2tp application parameter logging file {config.get(section,'logging-file')}\n"
    commands += f"set l2tp application parameter logging session {config.get(section,'logging-session')}\n"
    commands += f"set l2tp application parameter logging syslog {config.get(section,'logging-syslog')}\n"
    commands += f"set l2tp application parameter pgw-address {config.get(section,'pgw-address-ipv4')}\n"
    commands += f"set l2tp application parameter pgw-port {config.get(section,'pgw-port')}\n"
    commands += f"set l2tp application parameter self-address {config.get(section,'self-address-ipv4')}\n"
    commands += f"set l2tp application parameter self-port {config.get(section,'self-port')}\n"
    commands += f"set l2tp application parameter session-id-end {config.get(section,'session-id-end')}\n"
    commands += f"set l2tp application parameter session-id-start {config.get(section,'session-id-start')}\n"
    commands += f"set l2tp application parameter session-timeout {config.get(section,'session-timeout')}\n"
    commands += f"set l2tp application parameter tunnel-timeout {config.get(section,'tunnel-timeout')}\n"
    commands += f"set l2tp capability max-session-supported {config.get(section,'max-session-supported')}\n"
    commands += f"set l2tp capability max-tunnel-supported {config.get(section,'max-tunnel-supported')}\n"
    commands += "set l2tp ppp profile pap-default auth-chap no\n"
    commands += "set l2tp ppp profile pap-default auth-pap yes\n"
    return commands

def generate_deployment_mode_commands(config, section):
    commands = ""
    if config.get(section, 'access-mode') == "L2":
        # L2GRE case
        if config.has_option(section, "twagdp-cp-dhcp-subnet-ipv4"):
            commands +=f"set service dhcp-relay listen-interface br10\n"
            commands +=f"set service dhcp-relay server {config.get('twagdp_config','twagcp-ipv4')}\n"
            commands +=f"set service dhcp-relay upstream-interface {config.get('default','ctrl-interface-name')}\n"
            commands +=f"set interfaces bridge br10 address {config.get(section,'twagdp-cp-dhcp-subnet-ipv4')}\n"
        # L2 case
        else:
            commands +=f"set interfaces bridge br10 address {config.get('fast_path_if_1', 'if-ipv4')}\n"
            if config.has_option('fast_path_if_1' , 'vlan_id'):
                commands += f"delete interfaces dataplane {config.get('fast_path_if_1', 'if_name')} vif {config.get('fast_path_if_1', 'vlan_id')} address {config.get('fast_path_if_1', 'if-ipv4')}\n"
                if config.has_option('fast_path_if_1' , 'if-ipv6'):
                    commands += f"delete interfaces dataplane {config.get('fast_path_if_1', 'if_name')} vif {config.get('fast_path_if_1', 'vlan_id')} address {config.get('fast_path_if_1', 'if-ipv6')}\n"
            else:
                commands += f"delete interfaces dataplane {config.get('fast_path_if_1', 'if_name')} address {config.get('fast_path_if_1', 'if-ipv4')}\n"
                if config.has_option('fast_path_if_1' , 'if-ipv6'):
                    commands += f"delete interfaces dataplane {config.get('fast_path_if_1', 'if_name')} address {config.get('fast_path_if_1', 'if-ipv6')}\n"

    return commands


def generate_twagdp_config_commands(config, section):
    """
    Generates configuration commands for TWAG Data Plane (DP) setup in network devices.

    Parameters:
        config (ConfigParser): Configuration object containing required keys:
            - [section] twagcp-ipv4 (mandatory control-plane IPv4 address)
            - Optional: twagdp-ipv4, twagdp-id, dpcp-port in [section]
            - Mandatory for HA: twagcp-node1-ipv4 and twagcp-node2-ipv4
        section (str): Section name containing TWAG DP settings. Must contain 'twagcp-ipv4'.

    Returns:
        str: Newline-separated configuration commands for TWAG DP setup.

    Behavior:
        1. Constructs base control-plane address from [section]twagcp-ipv4
        2. Derives data-plane address from either [section]twagdp-ipv4 or default.ctrl-ipv4 (CIDR format)
        3. Applies defaults: id=1, port=5010, interface=ens3 if unspecified
        4. Requires explicit HA configuration via node_1 and node_2 control-plane IPs
        5. Uses default.ctrl-interface-name for HA dataplane interface if available

    Note:
        - 'twagcp-node1-ipv4' and 'twagcp-node2-ipv4' are mandatory for HA configuration
        - 'ctrl-ipv4' must be in CIDR format (e.g., 192.168.1.1/24) as it's parsed with '/'
        - Default physical IP derives from default.ctrl-ipv4's network address
    """
    commands = ""
    commands += f"set service wigw twag control-plane address {config.get(section,'twagcp-ipv4')}\n"
    ctrl_ipv4 = config.get("default", "ctrl-ipv4")
    ctrl_ipv4_only = ctrl_ipv4.split("/")[0]
    commands += f"set service wigw twag data-plane address {ctrl_ipv4_only}\n"
    if config.has_option(section, "twagdp-id"):
        commands += (
            f"set service wigw twag data-plane id {config.get(section,'twagdp-id')}\n"
        )
    else:
        commands += f"set service wigw twag data-plane id 1\n"
    if config.has_option(section, "dpcp-port"):
        commands += (
            f"set service wigw twag data-plane port {config.get(section,'dpcp-port')}\n"
        )
    else:
        commands += f"set service wigw twag data-plane port 5010\n"
    commands += f"set service wigw twag enable\n"
    commands += f"set service wigw twag default-mode {config.get('deployment_mode','access-mode')}\n"
    if config.get('deployment_mode', 'access-mode') == "L2":
        commands +=f"set service wigw twag l2-access-iface br10\n"
        # L2 case
        if not config.has_option("deployment_mode", "twagdp-cp-dhcp-subnet-ipv4"):
            if config.has_option('fast_path_if_1' , 'vlan_id'):
                commands += f"set interfaces dataplane {config.get('fast_path_if_1', 'if_name')} vif {config.get('fast_path_if_1', 'vlan_id')} bridge-group bridge br10\n"
            else:
                commands += f"set interfaces dataplane {config.get('fast_path_if_1', 'if_name')} bridge-group bridge br10\n"
    commands += f"set service wigw haf control-plane node_1-ip address {config.get(section,'twagcp-node1-ipv4')}\n"
    commands += f"set service wigw haf control-plane node_2-ip address {config.get(section,'twagcp-node2-ipv4')}\n"
    if config.has_option("default", "ctrl-interface-name"):
        commands += f"set service wigw haf dataplane interface {config.get('default','ctrl-interface-name')}\n"
    else:
        commands += f"set service wigw haf dataplane interface eth1\n"
    commands += f"set service wigw haf dataplane physical-ip address {ctrl_ipv4_only}\n"
    commands +=f"set service wigw haf router-address address {config.get('default','ctrl-gw-ipv4')}\n"
    if config.has_option(section, "max-ap"):
        commands += (
            f"set service wigw twag profile max-ap {config.get(section,'max-ap')}\n"
        )
    else:
        commands += f"set service wigw twag profile max-ap 16000\n"
    if config.has_option(section, "max-subscribers"):
        commands += (
            f"set service wigw twag profile max-subscribers {config.get(section,'max-subscribers')}\n"
        )
    else:
        commands += f"set service wigw twag profile max-subscribers 1000000\n"
    if config.has_option(section, "max-tunnel"):
        commands += (
            f"set service wigw twag profile max-tunnel {config.get(section,'max-tunnel')}\n"
        )
    else:
        commands += f"set service wigw twag profile max-tunnel 2000000\n"
    if config.has_option(section, "max-bandwidth"):
        commands += (
            f"set service wigw twag profile max-bandwidth {config.get(section,'max-bandwidth')}\n"
        )
    else:
        commands += f"set service wigw twag profile max-bandwidth 999999999\n"
    commands += f"set service wigw twag ratelimit enabled\n"
    if config.has_option('fast_path_if_2' , 'vlan_id'):
        commands += f"set service wigw twag s2a interface {config.get('fast_path_if_2', 'if_name')}.{config.get('fast_path_if_2', 'vlan_id')}\n"  
    if config.has_option(section, "access-ipv4"):
       commands += (
           f"set service wigw twag access ip {config.get(section,'access-ipv4')}\n"
       )
    if config.has_option(section, "access-ipv6"):
       commands += (
           f"set service wigw twag access ip6 {config.get(section,'access-ipv6')}\n"
       )

    return commands


def generate_twagdp_ap_config_commands(config, section):
    """
    Generates configuration commands for a TWAG AP (Termination Access Gateway).

    Constructs configuration commands based on parameters in the specified section of the config.
    Requires 'ap-ipv4' and 'ap-side-interface-name' keys in the config section. Sets 'ap-mode'
    to L2 by default if unspecified. Commands are formatted as newline-separated strings for
    applying network service configurations.

    Parameters:
        config (ConfigParser-like): Configuration object with sections and key-value pairs.
        section (str): Name of the configuration section containing TWAG AP parameters.

    Returns:
        str: Newline-separated configuration commands in the format:
            'set service wigw twag ap <IP> interface <INTERFACE>\n'
            'set service wigw twag ap <IP> mode <MODE>\n'

    Example:
        Given config[section] contains:
            ap-ipv4 = 192.168.1.1
            ap-side-interface-name = eth0
            ap-mode = L3
        Returns:
            'set service wigw twag ap 192.168.1.1 interface eth0\n'
            'set service wigw twag ap 192.168.1.1 mode L3\n'

    Note:
        - 'ap-ipv4' and 'ap-side-interface-name' are mandatory; missing keys will raise KeyError.
        - 'ap-mode' supports values like 'L2' (default) and 'L3'; other values may be system-specific.
        - Generated commands align with TWAG DP configuration schema for interface/mode settings.
    """

    match = re.search(r'ap_config_(\d+)', section)
    if not match:
        raise ValueError(f"Invalid section name: {section}")
    ap_id = match.group(1)
    commands = ""
    if config.get('deployment_mode', 'access-mode') == "L2":
        commands += f"set interfaces tunnel tun{ap_id} bridge-group bridge br10\n"
        commands += f"set interfaces tunnel tun{ap_id} encapsulation gre-bridge\n"
    else:
        commands += f"set interfaces tunnel tun{ap_id} encapsulation gre\n"
        # l3 gre tunnels need ip
    commands += f"set interfaces tunnel tun{ap_id} local-ip {config.get('fast_path_if_1','if-ipv4').split('/')[0]}\n"
    commands += f"set interfaces tunnel tun{ap_id} remote-ip {config.get(section,'ap-ipv4')}\n"


    return commands


def generate_lb_global_config_commands(config, section):
    """
    Generates configuration commands for load balancer global settings based on configuration data.

    This function constructs CLI-style configuration commands by checking options in the provided
    ConfigParser object under the specified section. It handles CPU affinity settings, IKE/ESP SPI
    timeouts, Ipp port timeout, and BGP autonomous system number configuration. Commands are generated
    with default values when options are missing, except for required BGP ASN.

    Parameters:
    config (ConfigParser): Configuration data source
    section (str): Configuration section containing load balancer settings

    Returns:
    str: Newline-separated string of configuration commands\n
    Configuration Options:
    - gc-cpu-affinity (int, default=1): CPU affinity for garbage collector thread
    - ike-init-timeout (int, default=10s): IKE initialization timeout
    - ike-spi-timeout (int, default=120s): IKE SPI allocation timeout
    - ipp-timeout (int, default=120s): IP-port timeout duration
    - esp-spi-timeout (int, default=120s): ESP SPI allocation timeout
    - bgp-asn (required): BGP autonomous system number (no default value)

    Command Mapping:
    - gc-cpu-affinity -> 'set system default load-balancer gc cpu-affinity'
    - ike-init-timeout -> 'set service load-balancer tuning ike-init timeout'
    - ike-spi-timeout -> 'set service load-balancer tuning ike-spi timeout'
    - ipp-timeout -> 'set service load-balancer tuning ip-port timeout'
    - esp-spi-timeout -> 'set service load-balancer tuning esp-spi timeout'
    - bgp-asn -> 'set protocols bgp <asn> address-family ipv4-unicast'

    Example:
    For configuration:
        [load-balancer]
        gc-cpu-affinity = 2
        ike-init-timeout = 15
        bgp-asn = 65000
    Generates:
        set system default load-balancer gc cpu-affinity 2\n
        set service load-balancer tuning ike-init timeout 15\n
        set protocols bgp 65000 address-family ipv4-unicast\n
    Note: Each command is terminated with a newline (\n) including trailing space character
    """
    commands = ""
    commands += f"set routing ecmp mode modulo-n\n"
    commands += f"set system default dataplane cpu-affinity 3-9\n"
    if config.has_option(section, "gc-cpu-affinity"):
        commands += f"set system default load-balancer gc cpu-affinity {config.get(section,'gc-cpu-affinity')}\n"
    else:
        commands += f"set system default load-balancer gc cpu-affinity 1\n"
    if config.has_option(section, "ike-init-timeout"):
        commands += f"set service load-balancer tuning ike-init timeout {config.get(section,'ike-init-timeout')}\n"
    else:
        commands += f"set service load-balancer tuning ike-init timeout 10\n"
    if config.has_option(section, "ike-spi-timeout"):
        commands += f"set service load-balancer tuning ike-spi timeout {config.get(section,'ike-spi-timeout')}\n"
    else:
        commands += f"set service load-balancer tuning ike-spi timeout 120\n"
    if config.has_option(section, "ipp-timeout"):
        commands += f"set service load-balancer tuning ip-port timeout {config.get(section,'ipp-timeout')}\n"
    else:
        commands += f"set service load-balancer tuning ip-port timeout 120\n"
    if config.has_option(section, "esp-spi-timeout"):
        commands += f"set service load-balancer tuning esp-spi timeout {config.get(section,'esp-spi-timeout')}\n"
    else:
        commands += f"set service load-balancer tuning esp-spi timeout 120\n"

    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} address-family ipv4-unicast\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} parameters ebgp-requires-policy disabled\n"

    return commands

def generate_lb_config_commands(config, section):
    """
    Generates configuration commands for load balancer clusters and BGP neighbors based on
    configuration settings in a specified section of a ConfigParser object.

    Args:
        config (ConfigParser): Configuration object containing network parameters.
        section (str): Section in config containing load balancer/BGP settings.

    Returns:
        str: Concatenated string of configuration commands for load balancer clusters and BGP neighbors.

    Behavior Details:
    1. Creates load balancer cluster with:
        - Cluster IPv4 from 'cluster-ipv4'
        - Cluster name from 'cluster-name'
    2. Processes node entries matching 'node{N}-ipv4' pattern:
        a) Extracts node number via regex
        b) Uses corresponding 'bgp-node{N}-asn' for neighbor configuration
        c) Adds commands to:
            - Associate nodes with the cluster
            - Configure BGP neighbors with remote ASNs and update sources
    3. Utilizes global settings from section:
        - BGP ASN from 'bgp-asn'
        - Update source IP from 'bgp-update-source-ipv4'

    Configuration Requirements:
    Required keys in config[section]:
    - 'cluster-ipv4', 'cluster-name', 'bgp-asn', 'bgp-update-source-ipv4'
    - At least one 'nodeX-ipv4' key (X=integer) with matching 'bgp-nodeX-asn' key

    Error Handling:
    - Silent failures for invalid/mismatched keys (returns partial commands)
    - Regex validation ensures only properly formatted node entries are processed

    Integration Context:
    - Typically called by deployment scripts handling network device provisioning
    - Output is used with configuration management systems to apply settings to routers/load balancers
    """
    commands = ""
    commands += f"set service load-balancer cluster {config.get(section,'cluster-ipv4')} name {config.get(section,'cluster-name')}\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} parameters ebgp-requires-policy disabled\n"
    commands += f"set system host-name {config.get(section, 'lb-hostname')}\n"

    commands += f"set policy route route-map LB-HA-ROUTE-MAP\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} neighbor {config.get(section, 'bgp-router-ip')} address-family ipv4-unicast route-map export LB-HA-ROUTE-MAP\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} neighbor {config.get(section, 'bgp-router-ip')} address-family ipv4-unicast soft-reconfiguration inbound\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} neighbor {config.get(section, 'bgp-router-ip')} remote-as {config.get(section,'bgp-router-asn')}\n"
    commands += f"set protocols bgp {config.get(section, 'bgp-asn')} neighbor {config.get(section, 'bgp-router-ip')} update-source {config.get(section, 'bgp-router-update-source-ipv4')}\n"

    for key in config.options(section):

        if key.startswith("node") and key.endswith("-ipv4") and "mgmt" not in key:
            m = re.search("node([0-9]+)-ipv4", key)
            if m:
                n = m.group(1)
            node_asn_var = f"bgp-node{n}-asn"
            node_ip = config.get(section, key)
            mgmt_key = f"node{n}-mgmt-ipv4"
            bgp_asn = config.get(section, "bgp-asn")
            mgmt_ip = config.get(section, mgmt_key)
            hostname_key = f"node{n}-hostname"
            hostname_val = config.get(section,hostname_key)
            commands += f"set service load-balancer cluster {config.get(section,'cluster-ipv4')} node {node_ip} mgmt-ip {mgmt_ip}\n"
            commands += f"set service load-balancer cluster {config.get(section,'cluster-ipv4')} node {node_ip} hostname {hostname_val}\n"
            commands += f"set protocols bgp {bgp_asn} neighbor {node_ip} remote-as {config.get(section, node_asn_var)}\n"
            commands += f"set protocols bgp {bgp_asn} neighbor {node_ip} update-source {config.get(section, 'bgp-update-source-ipv4')}\n"
            commands += f"set protocols bgp {bgp_asn} neighbor {node_ip} address-family ipv4-unicast soft-reconfiguration inbound\n"
            commands += f"set system syslog file dp-lb.txt msg regex {hostname_val}\n"

    commands += f"set system syslog file dp-lb.txt archive files 5\n"
    commands += f"set system syslog file dp-lb.txt archive size 500000\n"

    return commands



def generate_HA_lb_config_commands(config, section):
    epdg_cluster_name = config.get("lb_config_1", "cluster-name")
    virtual_ip = config.get(section, 'virtual-ip')
    base_if = config.get("fast_path_if_2", "if_name")
    vlan = config.get("fast_path_if_2", "vlan_id")
    full_interface = f"{base_if}.{vlan}"
    commands = ""

    # Set HA cluster name
    commands += f"set service load-balancer ha-cluster name {config.get(section,'ha-cluster-name')}\n"

    # Loop over keys and find all ha-cluster-node-ipX entries
    for key in config.options(section):
        if key.startswith("ha-cluster-node-ip"):
            # Extract the node index (1, 2, 3...)
            m = re.search(r"ha-cluster-node-ip(\d+)", key)
            if not m:
                continue
            idx = m.group(1)   # example: "1"

            # Build the matching name key
            name_key = f"ha-cluster-node-name{idx}"

            # Get IP and Name from config
            node_ip = config.get(section, key)
            node_name = config.get(section, name_key)

            # Generate the command
            commands += f"set service load-balancer ha-cluster node {node_name} ip {node_ip}\n"

    commands += (
        f"set service load-balancer ha-cluster schedule {epdg_cluster_name} virtual-ip {virtual_ip}\n"
    )
    commands += (
        f"set service load-balancer ha-cluster schedule {epdg_cluster_name} interface {full_interface}\n"
    )

    return commands

def generate_global_bgp_commands(config, section):
    commands = ""
    commands += f"set protocols bgp {config.get(section, 'self-as')} parameters ebgp-requires-policy disabled\n"
    if config.has_option(section, "self-as"):
        if config.get(section, "ipv4-unicast") == "true":
            commands += f"set protocols bgp {config.get(section, 'self-as')} address-family ipv4-unicast\n"
        if config.get(section, "ipv6-unicast") == "true":
            commands += f"set protocols bgp {config.get(section, 'self-as')} address-family ipv6-unicast\n"

    return commands


def generate_neighbour_bgp_commands(config, section):
    commands = ""
    if config.has_section("global_bgp"):
        if config.has_option("global_bgp", "ipv4-unicast") and config.has_option("global_bgp", "self-as"):
            if config.get("global_bgp", "ipv4-unicast") == "true":
                if config.has_option(section, "neighbor-ipv4"):
                    commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv4')} address-family ipv4-unicast soft-reconfiguration inbound\n"
                    if config.has_option(section, "remote-as"):
                        commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv4')} remote-as {config.get(section, 'remote-as')}\n"
                    if config.has_option(section, "update-source-ipv4"):
                        commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv4')} update-source {config.get(section, 'update-source-ipv4')}\n"

    if config.has_section("global_bgp"):
        if config.has_option("global_bgp", "ipv6-unicast") and config.has_option("global_bgp", "self-as"):
            if config.get("global_bgp", "ipv6-unicast") == "true":
                if config.has_option(section, "neighbor-ipv6"):
                    commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv6')} address-family ipv6-unicast soft-reconfiguration inbound\n"
                    if config.has_option(section, "remote-as"):
                        commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv6')} remote-as {config.get(section, 'remote-as')}\n"
                    if config.has_option(section, "update-source-ipv6"):
                        commands += f"set protocols bgp {config.get('global_bgp', 'self-as')} neighbor {config.get(section, 'neighbor-ipv6')} update-source {config.get(section, 'update-source-ipv6')}\n"

    return commands


################################################################################
# Based on matched section call function to generate cli commands.             #
################################################################################
def generate_cli_commands(config, section):
    # default should be the very first block in cfg section
    if section == "default":
        return generate_node_based_values_and_commands(config, section)

    if section == "snmp":
        return generate_snmp_commands(config, section)

    if section.startswith("tacacs_"):
        return generate_tacacs_commands(config, section)

    if section.startswith("static_route_ipv4_"):
        return generate_static_route_ipv4_commands(config,section)

    if section.startswith("static_route_ipv6_"):
        return generate_static_route_ipv6_commands(config,section)

    if section == "sts":
        return generate_sts_commands(config, section)

    if section == "l2tp_sts":
        return generate_l2tp_sts_commands(config, section)

    if section.startswith("ipdr_"):
        return generate_ipdr_commands(config, section)

    if section == "hamon_reporter" and config.get("default", "node-name") not in ["dpi", "secgw"]:
        return generate_hamon_reporter_commands(config, section)

    if section.startswith("ntp_"):
        return generate_ntp_commands(config, section)

    if section == "ssh":
        return generate_ssh_commands(config, section)

    if section == "os_hardening":
        return generate_os_hardening_commands(config, section)

    if section.startswith("syslog_"):
        return generate_syslog_commands(config, section)

    if section.startswith("fast_path_if_"):
        return generate_set_interface_commands(config, section)

    if section.startswith("sys_path_if_"):
        return generate_system_interface_commands(config, section)

    if section == "firewall_default":
        return generate_firewall_default_commands(config, section)

    if section == "firewall_test_default":
        return generate_firewall_test_default_commands(config, section)

    if section.startswith("fwruleset_"):
        return generate_firewall_ruleset_commands(config, section)

    if section.startswith("fw_attached_to_interface_"):
        return generate_fw_attached_to_interface_commands(config, section)

    if section.startswith("zone_creation_"):
        return generate_zone_creation_commands(config, section)

    if section.startswith("local_zone_creation_"):
        return generate_local_zone_creation_commands(config, section)

    if section.startswith("zone_communication_"):
        return generate_zone_communication_commands(config, section)

    if section == "secgw-ha":
        return generate_secgw_ha_commands(config, section)

    if section.startswith("cgnat44_"):
        return generate_cgnat44_config_commands(config, section)

    if section.startswith("cgnat64_"):
        return generate_cgnat64_config_commands(config, section)

    if section.startswith("cgnat44-Passthrough_"):
        return generate_cgnat44_passthrough_config_commands(config, section)

    if section.startswith("cgnat64-Passthrough_"):
        return generate_cgnat64_passthrough_config_commands(config, section)

    if section.startswith("dpi_"):
        return generate_dpi_config_commands(config, section)

    if section.startswith("cips_"):
        return generate_cips_config_commands(config, section)

    if section.startswith("update_cips_sig"):
        return update_cips_signature_command(config, section)

    if section == "imsdp":
        return generate_imsdp_commands(config, section)

    if section == "lac":
        return generate_lac_config_commands(config, section)

    if section.startswith("pod_"):
        return generate_imsdp_pod_config_commands(config, section)

    if section.startswith("host_firewall"):
        return generate_host_firewall_commands(config, section)

    if section.startswith("host_fw_whitelist"):
        return generate_host_fw_whitelist_ipv4_commands(config, section)

    if section == "epdg_ipsec_profile":
        return generate_epdg_ipsec_profile_config_commands(config, section)

    if section == "epdg_config":
        return generate_epdg_config_commands(config, section)
    
    if section.startswith("epdg_node_"):
        return generate_haf_mdp_commands(config, section)
    
    if section.startswith("epdg_pcscf_") or section.startswith("epdg_imsdp_") :
        return generate_epdg_pcscf_imsdp_route_config_commands(config, section)
    
    if section.startswith("epdg_pgwdp_"):
        return generate_epdg_pgwdp_route_config_commands(config, section)
    if section == "deployment_mode":
        return generate_deployment_mode_commands(config, section)

    if section == "twagdp_config":
        return generate_twagdp_config_commands(config, section)

    if section.startswith("ap_config_"):
        return generate_twagdp_ap_config_commands(config, section)

    if section == "lb_global_config":
        return generate_lb_global_config_commands(config, section)

    if section.startswith("lb_config_"):
        return generate_lb_config_commands(config, section)

    if section.startswith("HA_lb_config_"):
        return generate_HA_lb_config_commands(config, section)

    if section.startswith("global_bgp"):
        return generate_global_bgp_commands(config, section)

    if section.startswith("neighbor_bgp"):
        return generate_neighbour_bgp_commands(config, section)

    if section.startswith("vrf"):
        return generate_vrf_commands(config, section)

    return ""

################################################################################
# Modify only in sections above, specific to the individual module.            #
################################################################################
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

def commit_cli_commands(commands):
    f = open(CLI_FILE, "w")
    f.write("#!/bin/vcli -f\n")
    f.write("configure\n")
    f.write(f'{commands}')
    f.write("\ncommit\n")
    f.close()

    log("#!/bin/vcli -f\n")
    log("configure\n")
    log(f"CONFIG COMMANDS : \n{commands}")
    log("\ncommit\n")

    os.system(f"chmod +x {CLI_FILE}");
    commands = f"/opt/vyatta/sbin/lu --user configd {CLI_FILE}"
    ret = subprocess.run(
        commands,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    time.sleep(2)   # Wait after the commit command finishes
    return ret
    # return subprocess.run(['/opt/vyatta/sbin/lu', '--user configd', f'{CLI_FILE}'], capture_output=True, text=True)
    # return subprocess.run(['/bin/vcli', '-f', f'{CLI_FILE}'], capture_output=True, text=True)
    # return os.system(f"/bin/vcli -f {CLI_FILE}")
    # return os.system(f"/bin/bash ls ")


def list_interfaces(config):
    for section in config.sections():
        if section.startswith("fast_path_if_") or section.startswith("sys_path_if_"):
            if config.has_option(section , 'if-ipv4'):
                ip_with_mask = f"{config.get(section,'if-ipv4')}"
                ip = ip_with_mask.split('/')[0]
                if config.has_option(section, 'vlan_id'):
                    if_ipv4[f"{config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}"] = ip
                else:
                    if_ipv4[f"{config.get(section, 'if_name')}"] = ip
            if config.has_option(section , 'if-ipv6'):
                ip_with_mask = f"{config.get(section,'if-ipv6')}"
                ip = ip_with_mask.split('/')[0]
                if config.has_option(section, 'vlan_id'):
                    if_ipv6[f"{config.get(section, 'if_name')}.{config.get(section, 'vlan_id')}"] = ip
                else:
                    if_ipv6[f"{config.get(section, 'if_name')}"] = ip



def main():

    if "-h" in sys.argv or "-H" in sys.argv:
        print("""
Usage: python3 script.py [nodetype] [options]
[nodetype]:
  cips     - Run configuration for CIPS
  imsdp    - Run configuration for IMSDP
  epdgdp     - Run configuration for EPDGDP
  twagdp     - Run configuration for TWAGDP
  (default is CFW if not specified)
[options]:
  -w <filename> [section]
      Write CLI commands to /tmp/<filename>
      If [section] is provided, only commands from that section are written.
      Example: -w mycmds.txt             # write all sections
               -w mycmds.txt default      # write only [default] section
  -h or -H
      Show this help message and exit
Examples:
  python3 auto_config.py imsdp
  python3 auto_config.py cips -w output.txt
  python3 auto_config.py epdg -w commands.txt default
""")
        sys.exit(0)
    ################################################
    # Modify cfg file name based on input
    node_type = "cfw"  # default: for dpi, cfw, cgnat
    global CFG_FILE
    global LOGFILE_PATH

    if "cips" in sys.argv:
        CFG_FILE = "idp_config.cfg"
        LOGFILE_PATH = "/var/log/cips_nfv_configuration.log"
        node_type = "cips"
    elif "imsdp" in sys.argv:
        CFG_FILE = "imsdp_config.cfg"
        LOGFILE_PATH = "/var/log/imsdp_nfv_configuration.log"
        node_type = "imsdp"
    elif "epdgdp" in sys.argv or "twagdp" in sys.argv:
        CFG_FILE = "wigw_config.cfg"
        LOGFILE_PATH = "/var/log/wigw_nfv_configuration.log"
        # node_type = "epdgdp"
    elif "epdgdplb" in sys.argv:
        CFG_FILE = "epdgdplb_config.cfg"
        LOGFILE_PATH = "/var/log/epdgdplb_nfv_configuration.log"
    elif "hhe" in sys.argv:
        CFG_FILE = "hhe_config.cfg"
        LOGFILE_PATH = "/var/log/hhe_nfv_configuration.log"

    create_config_parser_input(CFG_FILE, NEW_FILE)

    config = configparser.ConfigParser()

    if not "cloud" in sys.argv:
        # non-cloud installation, no arguments
        config.read(NEW_FILE)
        if config.has_section("default") and config.has_section("CFG_VERSION"):
            if config.has_option("default", "node-name") and config.has_option(
                "CFG_VERSION", "version"
            ):
                if (
                    os.system(
                        f"python3 {VALIDATION_SCRIPT} {config.get('default', 'node-name')} {config.get('CFG_VERSION', 'version')}"
                    )
                    != 0
                ):
                    sys.exit(1)
            else:
                print(
                    "please enter node-name field in default section and version in CFG_VERSION section"
                )
                sys.exit(1)
        else:
            print("please enter default and CFG_VERSION section in cfg")
            sys.exit(1)

        if config.get('default', 'node-name') == "imsdp":
            os.system("mkdir -p /opt/cfw")
            os.system("mkdir -p /opt/cfw/snmp")
            os.system("mkdir -p /opt/cfw/eventhandler")
            os.system("rm -f /etc/snmp_info > /dev/null 2>&1")
            os.system("touch /etc/snmp_info")
            os.system(f"echo \"NODETYPE={config.get('snmp', 'node-type')}\"      >> /etc/snmp_info")
            os.system(f"echo \"DEVICENAME={config.get('snmp', 'device-name')}\"  >> /etc/snmp_info")
            os.system(f"echo \"REGIONNAME={config.get('snmp', 'region-name')}\"  >> /etc/snmp_info")
            if config.has_option('snmp', 'my-ipv4'):
                os.system(f"echo \"MYIP={config.get('snmp', 'my-ipv4')}\"      >> /etc/snmp_info")
            else:
                os.system(f"echo \"MYIP={config.get('default', 'mgmt-ipv4')}\"      >> /etc/snmp_info")
        else:
            os.system("mkdir -p /opt/cfw")
            os.system("mkdir -p /opt/cfw/snmp")
            os.system("mkdir -p /opt/cfw/eventhandler")
            os.system("rm -f /etc/snmp_info > /dev/null 2>&1")
            os.system("touch /etc/snmp_info")
            os.system(f"echo \"NODETYPE={config.get('snmp', 'node-type')}\"      >> /etc/snmp_info")
            os.system(f"echo \"DEVICENAME={config.get('snmp', 'device-name')}\"  >> /etc/snmp_info")
            os.system(f"echo \"REGIONNAME={config.get('snmp', 'region-name')}\"  >> /etc/snmp_info")
            if config.has_option('snmp', 'my-ipv4'):
                os.system(f"echo \"MYIP={config.get('snmp', 'my-ipv4')}\"      >> /etc/snmp_info")
            else:
                os.system(f"echo \"MYIP={config.get('default', 'mgmt-ipv4')}\"      >> /etc/snmp_info")
            os.system(f"echo \"PEERIP={config.get('snmp', 'peer-ipv4')}\"   >> /etc/snmp_info")
            os.system(f"echo \"VIP={config.get('snmp', 'vip-ipv4')}\"         >> /etc/snmp_info")
            os.system(f"echo \"MYIPV6={config.get('snmp', 'my-ipv6')}\"         >> /etc/snmp_info")
            os.system(f"echo \"PEERIPV6={config.get('snmp', 'peer-ipv6')}\"         >> /etc/snmp_info")
            os.system(f"echo \"GEOSITETYPE={config.get('snmp', 'geosite-type')}\"         >> /etc/snmp_info")
            os.system(f"echo \"PEERHOSTNAME={config.get('snmp', 'peer-host-name')}\"         >> /etc/snmp_info")
            os.system(f"echo \"SELFHOSTNAME={config.get('snmp', 'self-host-name')}\"         >> /etc/snmp_info")
            os.system(f"echo \"PR1IP={config.get('snmp', 'pr1-ipv4')}\"         >> /etc/snmp_info")
            os.system(f"echo \"PR2IP={config.get('snmp', 'pr2-ipv4')}\"         >> /etc/snmp_info")
            os.system(f"echo \"GR1IP={config.get('snmp', 'gr1-ipv4')}\"         >> /etc/snmp_info")
            os.system(f"echo \"GR2IP={config.get('snmp', 'gr2-ipv4')}\"         >> /etc/snmp_info")

    else:
        config.read(NEW_FILE)

    ################################################
    # Handle -w <file> [section] to write commands

    write_cmds = False
    target_section = None

    if "-w" in sys.argv:
        idx = sys.argv.index("-w") + 1
        try:
            file_name = f"/tmp/{sys.argv[idx]}"
            os.system(f"rm -rf {file_name}")
            write_cmds = True
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("-"):
                target_section = sys.argv[idx + 1]
        except IndexError:
            print("Please enter file name to write config commands")
            sys.exit(1)

    list_interfaces(config)

    for section in config.sections():
        if target_section and section != target_section:
            continue

        if section == "CFW_VERSION":
            continue

        commands = generate_cli_commands(config, section)

        print(f"{section}")
        print(commands)

        if write_cmds:
            with open(file_name, "a") as f:
                f.write(f"{commands}")
        else:
            ret = commit_cli_commands(commands)

            log(f"CONSOLE OUTPUT : {ret.stderr}\n{ret.stdout}\n")

            print(f"{ret.stderr}")
            print(f"{ret.stdout}")

if __name__ == "__main__":
    main()
