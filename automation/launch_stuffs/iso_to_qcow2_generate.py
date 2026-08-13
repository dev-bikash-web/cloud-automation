#! /usr/bin/env python3

from contextlib import contextmanager
import os
from time import sleep, time
from typing import Optional
import requests
from requests.auth import HTTPBasicAuth
import tempfile
import argparse
import pexpect
import logging

import dotenv

dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG") is not None else logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def getenv_required(key : str, default : Optional[str] = None):
    o = os.getenv(key)
    if o is None:
        if default is not None:
            return default
        raise ValueError(f"'{key}' not found in environment")
    return o

QCOW2_SIZE = int(getenv_required("QCOW2_SIZE", "50"))  # In GB
VM_RAM = int(getenv_required("VM_RAM", "32768"))  # In MB
VM_CPUS = int(getenv_required("VM_CPUS", "10"))

VM_HOST = getenv_required("VM_HOST", "192.168.111.150")
VM_HOST_USER = getenv_required("VM_HOST_USER", "ngn")
VM_HOST_PASS = getenv_required("VM_HOST_PASS", "ngn@8737")

IMAGE_USER = getenv_required("IMAGE_USER", "test")
IMAGE_PASS = getenv_required("IMAGE_PASS", "Test@1234")

"""
Host requirements (Assuming the host is running Ubuntu 24.04):
sudo apt install qemu-kvm libvirt-daemon libvirt-daemon-system virtinst guestfs-tools

sudo systemctl start libvirtd
sudo systemctl enable libvirtd

If the Host is a VM itself, make sure CPU Passthrough is enabled while creation. If you enable it 
after the VM's creation, you might have to run these commands so that Virtualization works:
rmmod kvm_intel
rmmod kvm
modprobe -r kvm
modprobe -r kvm_intel
(Use kvm_amd for AMD CPUs)

# Fo sudo-less access to libvirt
sudo usermod -aG libvirt $USER
"""

def get_iso(
    path: Optional[str] = None,
    url: Optional[str] = None,
    flavour: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    if path is None and url is None:
        raise ValueError("Either path or url must be provided")
    if flavour is None:
        raise ValueError("flavour must be provided")
    if path is not None and url is not None:
        raise ValueError("Only one of path or url should be provided")
    if path is not None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"ISO file not found at {path}")
        if not path.lower().endswith(".iso"):
            raise ValueError("Path is not a .iso file.")
        return path
    if url is not None:
        auth = None
        if username is not None and password is not None:
            auth = HTTPBasicAuth(username=username, password=password)
        logging.info("Downloading ISO...")
        response = requests.get(url, stream=True, auth=auth)
        if response.status_code != 200:
            if response.status_code == 403:
                raise ValueError(f"Failed to download ISO from {url} : Forbidden. Use the -h flag to see how you can pass credentials.")
            raise ValueError(f"Failed to download ISO from {url} : {response.status_code}")
        temp_iso = tempfile.NamedTemporaryFile(delete=False, suffix=".iso")
        with open(temp_iso.name, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_iso.name
    pass


@contextmanager
def use_ssh_session(host : str, username : str, password : str):
    try:
        logging.info(f"Connecting to {host} as {username}")
        ssh_session = pexpect.spawn(f"ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no {username}@{host}", timeout=300)
        
        # Define patterns to expect
        patterns = [
            "Are you sure you want to continue connecting (yes/no)?",  # First-time connection
            "password:",  # Prompt for password
            "Permission denied",  # Incorrect credentials
            pexpect.EOF,  # End of file (connection closed)
            pexpect.TIMEOUT  # Timeout
        ]

        # Wait for one of the patterns
        index = ssh_session.expect(patterns, timeout=10)

        if index == 0:  # First-time connection
            ssh_session.sendline("yes")
            ssh_session.expect("password:")  # Wait for password prompt
            ssh_session.sendline(password)
        elif index == 1:  # Password prompt
            ssh_session.sendline(password)
        elif index == 2:  # Permission denied
            logging.error("Permission denied. Check your credentials.")
            return
        elif index == 3:  # EOF
            logging.error("Connection closed unexpectedly.")
            return
        elif index == 4:  # Timeout
            logging.error("Connection timed out.")
            return
        ssh_session.expect("$")
        logging.info(f"Connected to {host}")
        yield ssh_session
        ssh_session.sendline("exit")
        ssh_session.expect(pexpect.EOF)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

def generate_qcow2(
    iso_path: str, 
    iso_flavour: str, 
    target_dir: Optional[str] = None, 
    file_name: Optional[str] = None
):
    if not os.path.exists(path=iso_path):
        raise FileNotFoundError(f"ISO file not found at {iso_path}")
    if target_dir is None:
        target_dir = os.getcwd()
    if file_name is None:
        file_name = os.path.basename(iso_path).removesuffix(".iso") + ".qcow2"
    final_filename = file_name
    file_name = "working_" + file_name
    iso_name = os.path.basename(iso_path)
    qcow2_path = os.path.join(target_dir, file_name)
    qcow2_path_final = os.path.join(target_dir, final_filename)
    vm_name = "AUTO_BUILD_" + final_filename.removesuffix(".qcow2")

    logging.info("Parameters passed to iso-to-qcow2 script - ")
    logging.info(f"VM_HOST - {VM_HOST} VM_HOST_USER-{VM_HOST_USER}, VM_HOST_PASS-{VM_HOST_PASS}")
    logging.info(f"QCOW2_SIZE - {QCOW2_SIZE} VM_RAM-{VM_RAM}, VM_CPUS - {VM_CPUS}")

    with use_ssh_session(VM_HOST, VM_HOST_USER, VM_HOST_PASS) as ssh_session:
        working_dir = f"/tmp/ccos_iso_to_qcow2_util"
        ssh_session.sendline(f"mkdir -p {working_dir}")
        ssh_session.sendline(f"cd {working_dir}")
        ssh_session.sendline("pwd")
        ssh_session.expect(working_dir)

        logging.info(f"Setting the HOST prompt as HOST$ for {VM_HOST}")
        ssh_session.sendline("export PS1='HOST$ '")
        ssh_session.expect("HOST\\$ ", timeout=60)
        
        ssh_session.logfile = open("pexpect_debug.log", "wb")
        ssh_session.logfile_read = ssh_session.logfile
        ssh_session.logfile_send = ssh_session.logfile

        logging.info("Transferring ISO File...")
        scp_session = pexpect.spawn(f"scp -o PreferredAuthentications=password -o PubkeyAuthentication=no {iso_path} {VM_HOST_USER}@{VM_HOST}:{working_dir}")
        scp_session.expect("password:")
        scp_session.sendline(VM_HOST_PASS)
        scp_session.sendline("pwd")
        scp_session.expect(pexpect.EOF, timeout=120)
        
        logging.info("Generating Empty QCow2...")
        ssh_session.sendline(f"rm -f {file_name}")
        ssh_session.sendline(f"qemu-img create -f qcow2 {file_name} {QCOW2_SIZE}G")
        ssh_session.sendline(f"find . -name {file_name}")
        ssh_session.expect(f"./{file_name}")
        logging.info("Empty QCow2 generated.")
        
        # Create a VM
        logging.info(f"Spawning a new VM : '{vm_name}' ...")

        ssh_session.expect("HOST\\$ ", timeout=60)
        # ssh_session.expect("$")
        ssh_session.sendline(f"virsh destroy {vm_name}")
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        ssh_session.sendline(f"virsh undefine {vm_name}")
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        vm_cmd = f"""virt-install --name "{vm_name}" --osinfo detect=on,require=off --ram "{VM_RAM}" --vcpus "{VM_CPUS}" --disk path="{working_dir}/{file_name}",size="{QCOW2_SIZE}",format=qcow2 --cdrom "{working_dir}/{iso_name}" --network none --noautoconsole"""
        logging.info("Running : " + vm_cmd)
        ssh_session.sendline(vm_cmd)
        ssh_session.expect("Starting install...")
        ssh_session.expect("Creating domain...")
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        ssh_session.sendline(f"virsh list --state-running | grep {vm_name}")
        ssh_session.expect(vm_name)
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        
        logging.info("Waiting for VM Bootup...")
        ssh_session.sendline(f"virsh console {vm_name} --force\n")
        ssh_session.expect(f"node login:", timeout=1440)
        ssh_session.sendline("")
        ssh_session.expect(f"node login:")
        ssh_session.sendline("tmpuser")
        ssh_session.expect(f"Password:")
        ssh_session.sendline("tmppwd")
        ssh_session.expect("$", timeout=60)

        logging.info("During VM install - Setting the VM operational-mode prompt as 'VM$ ' ")
        ssh_session.sendline("export PS1='VM$ '")
        ssh_session.expect("VM\\$ ", timeout=60)

        ssh_session.sendline("")
        ssh_session.expect("VM\\$ ", timeout=60)
        #ssh_session.expect("$", timeout=60)
        logging.info("Configuring...")
        ssh_session.sendline("install image")
        ssh_session.expect("What would you like to name this image?.*")
        ssh_session.sendline("")
        ssh_session.expect("Which one should I copy?.*")
        ssh_session.sendline("")
        ssh_session.expect("Enter username for administrator account:")
        ssh_session.sendline(IMAGE_USER)
        ssh_session.expect("Enter password", timeout=60)
        ssh_session.sendline(IMAGE_PASS)
        ssh_session.expect(f"Retype password for user '{IMAGE_USER}':", timeout=60)
        ssh_session.sendline(IMAGE_PASS)
        ssh_session.expect(r"Enter the desired system console \[tty0\]: ", timeout=60)
        logging.info(f"Created User {IMAGE_USER} , with password {IMAGE_PASS}")
        ssh_session.sendline("")
        ssh_session.expect(r"Would you like to setup a grub password\? \(Yes/No\) \[No\]: ", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Would you like to enable a reduced grub layout\? \(Yes/No\) \[No\]: ", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Install the image on\?", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Disk label type \(msdos/gpt\) \[gpt\]:", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Partition \(Auto/Parted\) \[Auto\]:", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Size of BIOS_BOOT partition\? \[256\]:", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"How much space would you like to allocate for the vRouter partition\?", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Size of the log partition\? \[0\]:", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Print final partition sizes\? \(Yes/No\) \[No\]:", timeout=60)
        ssh_session.sendline("")
        ssh_session.expect(r"Continue \(Yes/No\) \[No\]:", timeout=60)
        ssh_session.sendline("Yes")
        logging.info("Installing OS...")
        ssh_session.expect("Running post-install script...", timeout=200)
        ssh_session.expect("Done.", timeout=200)
        ssh_session.expect("VM\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)
        ssh_session.sendline("")
        ssh_session.expect("VM\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)
        logging.info("Installation successful.")
        
        logging.info("Turning off VM...")
        ssh_session.sendcontrol("]")
        sleep(5)
        ssh_session.expect("HOST\\$ ", timeout=90)
        #ssh_session.expect("$", timeout=60)
        ssh_session.sendline(f"virsh destroy {vm_name}")
        ssh_session.expect("HOST\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)
        ssh_session.sendline("")
        ssh_session.expect("HOST\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)
        
        logging.info("Restarting VM...")
        ssh_session.sendline(f"virsh start {vm_name}")
        ssh_session.expect(f"started", timeout=720)
        ssh_session.expect("HOST\\$ ", timeout=90)
        #ssh_session.expect("$", timeout=60)
        ssh_session.sendline(f"virsh console {vm_name} --force\n")
        ssh_session.expect(f"node login:", timeout=720)
        ssh_session.sendline("")
        ssh_session.expect(f"node login:")
        ssh_session.sendline(IMAGE_USER)
        ssh_session.expect(f"Password:")
        ssh_session.sendline(IMAGE_PASS)
        ssh_session.expect("$", timeout=200)

        logging.info("After installation - Setting the VM operational-mode prompt as 'VM$ ' ")
        ssh_session.sendline("export PS1='VM$ '")
        ssh_session.expect("VM\\$ ", timeout=60)

        ssh_session.sendline("configure")
        ssh_session.expect("#", timeout=200)

        logging.info("Setting the VM configure-mode prompt as 'VM# ' ")
        ssh_session.sendline("export PS1='VM# '")
        ssh_session.expect("VM\\# ", timeout=60)

        logging.info(f"Step to configure user as a Superuser")
        ssh_session.sendline(f"set system login user {IMAGE_USER} level superuser")
        ssh_session.expect("VM\\# ", timeout=60)
        #ssh_session.expect("#", timeout=60)
        ssh_session.sendline("commit")
        ssh_session.expect("VM\\# ", timeout=60)
        #ssh_session.expect("#", timeout=60)
        logging.info(f"{IMAGE_USER} is configured as a Superuser")
        ssh_session.sendline("exit")
        ssh_session.expect("VM\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)
        ssh_session.sendline(f"logout")


        logging.info(f"Step to start cloud-init changes in bootloader.")
        ssh_session.expect("node login:", timeout=200)
        ssh_session.sendline(IMAGE_USER)
        ssh_session.expect("Password:", timeout=200)
        ssh_session.sendline(IMAGE_PASS)
        ssh_session.expect("$", timeout=200)

        logging.info("Setting the VM operational-mode prompt as 'VM$ ' ")
        ssh_session.sendline("export PS1='VM$ '")
        ssh_session.expect("VM\\$ ", timeout=60)

        ssh_session.sendline("sudo su")
        ssh_session.expect(rf"\[sudo\] password for {IMAGE_USER}:")
        ssh_session.sendline(IMAGE_PASS)
        ssh_session.expect("#")

        logging.info("Setting the VM sudo prompt as 'VMSUDO# ' ")
        ssh_session.sendline("export PS1='VMSUDO# '")
        ssh_session.expect("VMSUDO\\# ", timeout=60)

        ssh_session.sendline("grep -q \"cloud-init\" /boot/grub/grub.cfg || sed -i \"s/linux \\(.*\\)/linux \\1 cloud-init/\" /boot/grub/grub.cfg") # enable cloud init if not already enabled
        ssh_session.expect("VMSUDO\\# ", timeout=60)
        #ssh_session.expect("#")
        ssh_session.sendline("rm -fr /var/lib/dhcp/*") # cleanup to make sure the instances will be unique
        ssh_session.expect("VMSUDO\\# ", timeout=60)
        #ssh_session.expect("#")
        ssh_session.sendline("echo -n > /etc/machine-id")
        ssh_session.expect("VMSUDO\\# ", timeout=230)
        #ssh_session.expect("#", timeout=200)
        logging.info(f"cloud-init is now enabled in bootloader.")

        #if iso_flavour in ("CIPS", "PROXY", "L2TP"):
        logging.info(f"Step to exclude interface dataplane.")
        ssh_session.sendline(f"bash /opt/vyatta/sbin/exclude-if-dataplane.sh {iso_flavour}")
        ssh_session.expect("VMSUDO\\# ", timeout=330)
        logging.info(f"Execution of exclude interface dataplane script done.")

        ssh_session.sendline("exit")
        ssh_session.expect("VM\\$ ", timeout=130)
        #ssh_session.expect("$", timeout=100)

        logging.info(f"Step to delete the user - {IMAGE_USER}")
        ssh_session.sendline("configure")
        ssh_session.expect("#", timeout=200)

        logging.info("Setting the VM configure-mode prompt as 'VM# ' ")
        ssh_session.sendline("export PS1='VM# '")
        ssh_session.expect("VM\\# ", timeout=60)

        ssh_session.sendline(f"delete system login user {IMAGE_USER}")
        ssh_session.expect("VM\\# ", timeout=60)
        #ssh_session.expect("#", timeout=60)
        ssh_session.sendline("commit")
        ssh_session.expect("VM\\# ", timeout=60)
        #ssh_session.expect("#", timeout=60)
        ssh_session.sendline("exit")
        ssh_session.expect("VM\\$ ", timeout=230)
        #ssh_session.expect("$", timeout=200)

        ssh_session.sendline("poweroff")
        ssh_session.expect(r"Proceed with poweroff\? \(Yes/No\) \[No\]", timeout=200)
        ssh_session.sendline("Yes")
        logging.info(f"Powering off...")
        ssh_session.expect("VM\\$ ", timeout=750)
        #ssh_session.expect("$", timeout=720)
        ssh_session.sendline("")
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        
        sleep(5)
        logging.info("Removing VM...")
        ssh_session.sendline(f"virsh undefine {vm_name}")
        ssh_session.expect(f"has been undefined")
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        logging.info("VM removed.")
        
        logging.info("Sparsifying QCow2...")
        ssh_session.sendline(f"sudo virt-sparsify {working_dir}/{file_name} --compress {working_dir}/{final_filename}") # apt install guestfs-tools
        if ssh_session.expect([f"password for {VM_HOST_USER}:", "Sparsify operation completed with no errors."], timeout=720) == 0:
            ssh_session.sendline(VM_HOST_PASS)
            ssh_session.expect("Sparsify operation completed with no errors.", timeout=720)
        logging.info("QCow2 sparsified.")
        
        logging.info("Emitting QCow2 Image...")
        scp_cmd = f"scp -o PreferredAuthentications=password -o PubkeyAuthentication=no {VM_HOST_USER}@{VM_HOST}:{working_dir}/{final_filename} ."
        logging.info(f"Running : {scp_cmd}")
        scp_session = pexpect.spawn(scp_cmd)
        scp_session.expect("password:")
        scp_session.sendline(VM_HOST_PASS)
        scp_session.sendline("pwd")
        scp_session.expect(pexpect.EOF, timeout=600)
        
        logging.info("Cleaning up artifacts...")
        ssh_session.sendline(f"rm -f {working_dir}/{iso_name}") #ISO
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        ssh_session.sendline(f"rm -f {working_dir}/{file_name}") #QCOW2 Working
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        ssh_session.sendline(f"rm -f {working_dir}/{final_filename}") #QCOW2 Final
        ssh_session.expect("HOST\\$ ", timeout=60)
        #ssh_session.expect("$")
        logging.info("Done.")
        logging.info(f"QCow2 Image saved as {final_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser("CCOS ISO to QCow2 Utility")

    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--iso-path", dest="iso_path")
    g.add_argument("--iso-url", dest="iso_url")
    parser.add_argument("--iso-url-username", dest="iso_url_username")
    parser.add_argument("--iso-url-password", dest="iso_url_password")
    parser.add_argument("--iso-flavour", dest="iso_flavour", required=True,
                    choices=["CFW", "CGNAT", "DPI", "EPDG", "EPDG_LB", "TWAG", "CIPS", "PROXY", "SECGW", "L2TP", "IMSDP"])

    args = parser.parse_args()
    start_time = time()

    iso_flavour = args.iso_flavour

    try:
        iso_path = get_iso(
            path=getattr(args, "iso_path", None), 
            url=getattr(args, "iso_url", None),
            flavour=getattr(args, "iso_flavour", None),
            username=getattr(args, "iso_url_username", None),
            password=getattr(args, "iso_url_password", None),
        )
        logging.info(f"ISO At : {iso_path}")
        logging.info(f"ISO Flavour : {iso_flavour}")
        generate_qcow2(iso_path=iso_path,iso_flavour=iso_flavour)
        
        end_time = time()
        logging.info(f"Generation Time: {end_time - start_time} seconds")
    except Exception as e:
        logging.error(e)
        raise SystemExit(1)
