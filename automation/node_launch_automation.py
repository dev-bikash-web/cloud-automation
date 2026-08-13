#!/usr/bin/env python3
"""
Node Launch Automation Script
Direct execution with zero local wrapper functions.
- run_cmd returns {"exit_code": int, "stdout": str, "stderr": str}
- execute_and_match returns {"match": bool, "stdout": str, "stderr": str}
"""

import os
import re
import glob
import hashlib
import asyncio
from typing import Dict, Any

from automation_framework import (
    ConfigParser,
    SSHNode,
    PipelineEngine,
    Step,
    log_info,
    log_success,
    log_error
)

def compute_local_file_md5(path: str) -> str:
    """Helper to compute local file MD5 using standard hashlib."""
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

# ==============================================================================
# ACTION COROUTINES (DIRECT EXECUTION)
# ==============================================================================

async def coro_01_parse_variables(ctx: Dict[str, Any]):
    """Action 1: Parse variables.txt and load configuration."""
    var_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variables.txt")
    log_info(f"Loading variables from: {var_file}")
    config = ConfigParser.parse(var_file)
    
    required_keys = [
        "CLOUD_CLI", "CLOUD_CLI_Password",
        "TEOSM_CLI", "TEOSM_CLI_Password",
        "TEOSM_CLI_OPTI_FOLDER", "CLOUD_NFV_FOLDER",
        "IMAGE_NAME", "CFG_FILE_NAME", "TEOSM_INSTANCE_NAME"
    ]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required variable in variables.txt: {key}")
            
    ctx["config"] = config
    log_success("variables.txt successfully parsed.")
    return config

async def coro_02_ssh_connect(ctx: Dict[str, Any]):
    """Action 2: Connect directly to specific machines using SSHNode."""
    config = ctx["config"]
    
    # 1. Connect CLOUD_CLI machine
    cloud_user, cloud_host, cloud_port = ConfigParser.get_host_credentials(config["CLOUD_CLI"])
    cloud_node = SSHNode(name="CLOUD_CLI", global_timeout=600)
    res1 = await cloud_node.connect(
        hostname=cloud_host,
        username=cloud_user,
        password=config["CLOUD_CLI_Password"],
        port=cloud_port
    )
    log_info(f"Connection Result 1: {res1['stdout']}")
    ctx["cloud_node"] = cloud_node

    # 2. Connect TEOSM_CLI machine
    teosm_user, teosm_host, teosm_port = ConfigParser.get_host_credentials(config["TEOSM_CLI"])
    teosm_node = SSHNode(name="TEOSM_CLI", global_timeout=600)
    res2 = await teosm_node.connect(
        hostname=teosm_host,
        username=teosm_user,
        password=config["TEOSM_CLI_Password"],
        port=teosm_port
    )
    log_info(f"Connection Result 2: {res2['stdout']}")
    ctx["teosm_node"] = teosm_node

    log_success("SSH connections established to both CLOUD_CLI and TEOSM_CLI.")

async def coro_03_verify_and_prepare_directories(ctx: Dict[str, Any]):
    """
    Action 3: Execute shell commands directly to verify remote directories.
    - Check CLOUD_NFV_FOLDER on CLOUD_CLI via command. Create if missing.
    - Check TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI via command. FAIL if missing!
    """
    cloud_node: SSHNode = ctx["cloud_node"]
    teosm_node: SSHNode = ctx["teosm_node"]
    config = ctx["config"]
    
    cloud_folder = config["CLOUD_NFV_FOLDER"]
    teosm_folder = config["TEOSM_CLI_OPTI_FOLDER"]

    # 1. Check CLOUD_NFV_FOLDER on CLOUD_CLI
    res_cloud = await cloud_node.run_cmd(f"test -d '{cloud_folder}'")
    if res_cloud["exit_code"] != 0:
        log_info(f"CLOUD_NFV_FOLDER '{cloud_folder}' missing on CLOUD_CLI. Executing mkdir command...")
        res_mkdir = await cloud_node.execute_and_match(
            command=f"mkdir -p '{cloud_folder}' && test -d '{cloud_folder}'",
            regex_pattern=r"^",
            expect_exit_code=0
        )
        if not res_mkdir["match"]:
            raise RuntimeError(f"Failed to create CLOUD_NFV_FOLDER '{cloud_folder}' on CLOUD_CLI: {res_mkdir['stderr']}")
    else:
        log_success(f"CLOUD_NFV_FOLDER '{cloud_folder}' verified on CLOUD_CLI.")

    # 2. Check TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI (Strict: fail if missing)
    res_teosm = await teosm_node.run_cmd(f"test -d '{teosm_folder}'")
    if res_teosm["exit_code"] != 0:
        raise FileNotFoundError(
            f"STRICT FAILURE: TEOSM_CLI_OPTI_FOLDER '{teosm_folder}' does NOT exist on TEOSM_CLI node! "
            f"Folder creation on TEOSM_CLI is forbidden."
        )
    log_success(f"Verified TEOSM_CLI_OPTI_FOLDER '{teosm_folder}' exists on TEOSM_CLI.")

async def coro_04_copy_stuffs_to_cloud(ctx: Dict[str, Any]):
    """Action 4: Upload NFV folder and qcow2 image directly to CLOUD_NFV_FOLDER on CLOUD_CLI using SFTP."""
    cloud_node: SSHNode = ctx["cloud_node"]
    config = ctx["config"]
    cloud_folder = config["CLOUD_NFV_FOLDER"]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    launch_stuffs_dir = os.path.join(base_dir, "launch_stuffs")
    
    nfv_local_dir = os.path.join(launch_stuffs_dir, "NFV")
    if not os.path.exists(nfv_local_dir):
        raise FileNotFoundError(f"Local NFV folder missing: {nfv_local_dir}")

    qcow2_files = glob.glob(os.path.join(launch_stuffs_dir, "*.qcow2"))
    if not qcow2_files:
        raise FileNotFoundError(f"No .qcow2 files found in {launch_stuffs_dir}")
    
    qcow2_local_path = qcow2_files[0]
    qcow2_filename = os.path.basename(qcow2_local_path)
    ctx["qcow2_filename"] = qcow2_filename

    # Direct SFTP directory upload
    remote_nfv_dir = os.path.join(cloud_folder, "NFV").replace('\\', '/')
    loop = asyncio.get_running_loop()

    def sync_upload_nfv():
        log_info(f"[CLOUD_CLI] Uploading NFV directory '{nfv_local_dir}' -> '{remote_nfv_dir}'...")
        for root, dirs, files in os.walk(nfv_local_dir):
            rel_path = os.path.relpath(root, nfv_local_dir)
            target_remote_dir = remote_nfv_dir if rel_path == '.' else os.path.join(remote_nfv_dir, rel_path).replace('\\', '/')
            try:
                cloud_node.sftp.stat(target_remote_dir)
            except IOError:
                cloud_node.sftp.mkdir(target_remote_dir)
            for file_name in files:
                local_file = os.path.join(root, file_name)
                remote_file = os.path.join(target_remote_dir, file_name).replace('\\', '/')
                cloud_node.sftp.put(local_file, remote_file)

    await loop.run_in_executor(None, sync_upload_nfv)

    # Direct SFTP file upload for qcow2
    remote_qcow2_path = os.path.join(cloud_folder, qcow2_filename).replace('\\', '/')
    log_info(f"[CLOUD_CLI] Uploading qcow2 file '{qcow2_local_path}' -> '{remote_qcow2_path}'...")
    await loop.run_in_executor(None, cloud_node.sftp.put, qcow2_local_path, remote_qcow2_path)

    ctx["qcow2_local_path"] = qcow2_local_path
    ctx["qcow2_remote_path"] = remote_qcow2_path
    log_success("Copied NFV folder and qcow2 file to CLOUD_CLI successfully.")

async def coro_05_verify_cloud_md5(ctx: Dict[str, Any]):
    """Action 5: Execute remote md5sum command on CLOUD_CLI directly and match with local MD5."""
    cloud_node: SSHNode = ctx["cloud_node"]
    config = ctx["config"]
    cloud_folder = config["CLOUD_NFV_FOLDER"]
    base_dir = os.path.dirname(os.path.abspath(__file__))
    launch_stuffs_dir = os.path.join(base_dir, "launch_stuffs")

    # 1. Verify qcow2 image MD5
    local_qcow2_path = ctx["qcow2_local_path"]
    remote_qcow2_path = ctx["qcow2_remote_path"]

    local_qcow2_md5 = compute_local_file_md5(local_qcow2_path)
    log_info(f"Local qcow2 MD5: {local_qcow2_md5}")

    cmd = f"md5sum '{remote_qcow2_path}'"
    regex_pattern = rf"^{re.escape(local_qcow2_md5)}\s+"
    
    res = await cloud_node.execute_and_match(cmd, regex_pattern=regex_pattern)
    log_info(f"qcow2 MD5 Result JSON: {res}")
    if not res["match"]:
        raise ValueError(f"MD5 MISMATCH for remote qcow2 image '{remote_qcow2_path}'. STDOUT: {res['stdout']}")

    # 2. Verify MD5 of NFV directory files
    nfv_local_dir = os.path.join(launch_stuffs_dir, "NFV")
    remote_nfv_dir = os.path.join(cloud_folder, "NFV").replace('\\', '/')
    
    for root, dirs, files in os.walk(nfv_local_dir):
        for f in files:
            loc_path = os.path.join(root, f)
            rel_path = os.path.relpath(loc_path, nfv_local_dir)
            rem_path = os.path.join(remote_nfv_dir, rel_path).replace('\\', '/')

            loc_md5 = compute_local_file_md5(loc_path)
            file_cmd = f"md5sum '{rem_path}'"
            file_regex = rf"^{re.escape(loc_md5)}\s+"

            file_res = await cloud_node.execute_and_match(file_cmd, regex_pattern=file_regex)
            if not file_res["match"]:
                raise ValueError(f"MD5 MISMATCH for file '{rel_path}' on CLOUD_CLI. STDOUT: {file_res['stdout']}")

    log_success("All MD5 checksums matched via command execution & regex output matching on CLOUD_CLI!")

async def coro_06_copy_cfg_cloud_to_teosm(ctx: Dict[str, Any]):
    """Action 6: Copy wigw_config.cfg directly from CLOUD_CLI to TEOSM_CLI using SFTP."""
    cloud_node: SSHNode = ctx["cloud_node"]
    teosm_node: SSHNode = ctx["teosm_node"]
    config = ctx["config"]

    cfg_file = config["CFG_FILE_NAME"]
    cloud_cfg_path = os.path.join(config["CLOUD_NFV_FOLDER"], "NFV", cfg_file).replace('\\', '/')
    teosm_cfg_path = os.path.join(config["TEOSM_CLI_OPTI_FOLDER"], cfg_file).replace('\\', '/')

    temp_local_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_temp_{cfg_file}")
    
    loop = asyncio.get_running_loop()
    log_info(f"Downloading '{cloud_cfg_path}' from CLOUD_CLI via SFTP...")
    await loop.run_in_executor(None, cloud_node.sftp.get, cloud_cfg_path, temp_local_cfg)

    log_info(f"Uploading '{cfg_file}' to TEOSM_CLI path '{teosm_cfg_path}' via SFTP...")
    await loop.run_in_executor(None, teosm_node.sftp.put, temp_local_cfg, teosm_cfg_path)

    if os.path.exists(temp_local_cfg):
        os.remove(temp_local_cfg)

    ctx["cloud_cfg_path"] = cloud_cfg_path
    ctx["teosm_cfg_path"] = teosm_cfg_path
    log_success(f"Copied {cfg_file} from CLOUD_CLI to TEOSM_CLI successfully.")

async def coro_07_verify_teosm_cfg_md5(ctx: Dict[str, Any]):
    """Action 7: Execute md5sum on CLOUD_CLI & TEOSM_CLI directly and verify with execute_and_match."""
    cloud_node: SSHNode = ctx["cloud_node"]
    teosm_node: SSHNode = ctx["teosm_node"]
    
    cloud_cfg_path = ctx["cloud_cfg_path"]
    teosm_cfg_path = ctx["teosm_cfg_path"]

    # 1. Execute md5sum on CLOUD_CLI directly
    res_cloud = await cloud_node.run_cmd(f"md5sum '{cloud_cfg_path}'")
    cloud_match = re.search(r"^([a-fA-F0-9]{32})\s+", res_cloud["stdout"].strip())
    if not cloud_match:
        raise RuntimeError(f"Could not extract MD5 from CLOUD_CLI output: {res_cloud['stdout']}")
    cloud_md5 = cloud_match.group(1)
    log_info(f"CLOUD_CLI CFG MD5: {cloud_md5}")

    # 2. Execute md5sum on TEOSM_CLI directly and match via Regex pattern
    teosm_cmd = f"md5sum '{teosm_cfg_path}'"
    teosm_regex = rf"^{re.escape(cloud_md5)}\s+"

    res = await teosm_node.execute_and_match(teosm_cmd, regex_pattern=teosm_regex)
    log_info(f"TEOSM MD5 Check Result JSON: {res}")
    if not res["match"]:
        raise ValueError(f"MD5 MISMATCH for CFG file on TEOSM_CLI!")

    log_success("CFG file MD5 checksum verified on TEOSM_CLI using regex matching.")

async def coro_08_create_openstack_image(ctx: Dict[str, Any]):
    """Action 8: Execute 'openstack image create' on CLOUD_CLI directly."""
    cloud_node: SSHNode = ctx["cloud_node"]
    config = ctx["config"]

    cloud_folder = config["CLOUD_NFV_FOLDER"]
    qcow2_filename = ctx.get("qcow2_filename", "*.qcow2")
    qcow2_path = os.path.join(cloud_folder, qcow2_filename).replace('\\', '/')
    image_name = config["IMAGE_NAME"]

    cmd = f"openstack image create '{image_name}' --disk-format qcow2 --file '{qcow2_path}' --public"
    regex_pattern = r"(status.*active|id.*[a-f0-9\-]{36}|" + re.escape(image_name) + r")"

    res = await cloud_node.execute_and_match(cmd, regex_pattern=regex_pattern, timeout=900)
    log_info(f"OpenStack Image Result JSON: {res}")
    if not res["match"]:
        raise RuntimeError(f"OpenStack Image Creation Failed! STDOUT: {res['stdout']}\nSTDERR: {res['stderr']}")

    log_success(f"OpenStack Image '{image_name}' created and verified via Regex.")

async def coro_09_run_replacevars_cloud(ctx: Dict[str, Any]):
    """Action 9: Execute 'echo -e "\n1" | ./replacevars.sh' on CLOUD_CLI directly."""
    cloud_node: SSHNode = ctx["cloud_node"]
    config = ctx["config"]

    nfv_remote_dir = os.path.join(config["CLOUD_NFV_FOLDER"], "NFV").replace('\\', '/')
    cmd = "chmod +x ./replacevars.sh && echo -e \"\\n1\" | ./replacevars.sh"
    regex_pattern = r".+"

    res = await cloud_node.execute_and_match(cmd, regex_pattern=regex_pattern, cwd=nfv_remote_dir, pty=True)
    log_info(f"replacevars.sh Result JSON: {res}")
    if not res["match"]:
        raise RuntimeError(f"replacevars.sh execution failed!")

    log_success("replacevars.sh executed and verified via Regex on CLOUD_CLI.")

async def coro_10_run_clean_teosm(ctx: Dict[str, Any]):
    """Action 10: Execute './clean.sh' in TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI directly."""
    teosm_node: SSHNode = ctx["teosm_node"]
    config = ctx["config"]

    opti_folder = config["TEOSM_CLI_OPTI_FOLDER"]
    cmd = "chmod +x ./clean.sh && ./clean.sh"
    regex_pattern = r".+"

    res = await teosm_node.execute_and_match(cmd, regex_pattern=regex_pattern, cwd=opti_folder, pty=True)
    log_info(f"clean.sh Result JSON: {res}")
    if not res["match"]:
        raise RuntimeError(f"clean.sh execution failed!")

    log_success("clean.sh executed and verified via Regex on TEOSM_CLI.")

async def coro_11_run_venv_teosm(ctx: Dict[str, Any]):
    """Action 11: Execute './venv.sh TEOSM_INSTANCE_NAME' in TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI directly."""
    teosm_node: SSHNode = ctx["teosm_node"]
    config = ctx["config"]

    opti_folder = config["TEOSM_CLI_OPTI_FOLDER"]
    instance_name = config["TEOSM_INSTANCE_NAME"]
    cmd = f"chmod +x ./venv.sh && ./venv.sh '{instance_name}'"
    regex_pattern = r".+"

    res = await teosm_node.execute_and_match(cmd, regex_pattern=regex_pattern, cwd=opti_folder, pty=True)
    log_info(f"venv.sh Result JSON: {res}")
    if not res["match"]:
        raise RuntimeError(f"venv.sh execution failed!")

    log_success("venv.sh executed and verified via Regex on TEOSM_CLI.")

async def coro_12_cleanup_cloud_folder(ctx: Dict[str, Any]):
    """Action 12 (Cleanup): Delete CLOUD_NFV_FOLDER on CLOUD_CLI machine directly."""
    cloud_node: SSHNode = ctx.get("cloud_node")
    config = ctx.get("config")
    
    if cloud_node and config:
        cloud_folder = config["CLOUD_NFV_FOLDER"]
        log_info(f"Cleaning up CLOUD_NFV_FOLDER '{cloud_folder}' on CLOUD_CLI via command execution...")
        
        cmd = f"rm -rf '{cloud_folder}' && test ! -d '{cloud_folder}'"
        res = await cloud_node.execute_and_match(cmd, regex_pattern=r"^", expect_exit_code=0)
        log_info(f"Cleanup Result JSON: {res}")
        if not res["match"]:
            raise RuntimeError(f"Failed to delete CLOUD_NFV_FOLDER '{cloud_folder}'")

        log_success(f"Successfully deleted CLOUD_NFV_FOLDER '{cloud_folder}' from CLOUD_CLI.")

async def coro_close_connections(ctx: Dict[str, Any]):
    """Close SSH Node connections."""
    cloud_node: SSHNode = ctx.get("cloud_node")
    teosm_node: SSHNode = ctx.get("teosm_node")
    if cloud_node:
        await cloud_node.close()
    if teosm_node:
        await teosm_node.close()

# ==============================================================================
# PIPELINE SETUP & MAIN
# ==============================================================================

def create_launch_pipeline() -> PipelineEngine:
    pipeline = PipelineEngine("Node Launch Automation Pipeline")

    pipeline.add_step(Step("Parse Variables", "Parse variables.txt configuration", coro_01_parse_variables))
    pipeline.add_step(Step("SSH Connect", "Login into CLOUD_CLI and TEOSM_CLI via SSH", coro_02_ssh_connect))
    pipeline.add_step(Step("Verify & Prepare Directories", "Command-based check of CLOUD_NFV_FOLDER & TEOSM_CLI_OPTI_FOLDER", coro_03_verify_and_prepare_directories))
    pipeline.add_step(Step("Copy Stuffs to CLOUD_CLI", "Upload NFV folder and qcow2 image to CLOUD_CLI", coro_04_copy_stuffs_to_cloud))
    pipeline.add_step(Step("Verify CLOUD_CLI MD5", "Command & Regex verification of MD5 sums on CLOUD_CLI", coro_05_verify_cloud_md5))
    pipeline.add_step(Step("Copy CFG to TEOSM_CLI", "Copy wigw_config.cfg from CLOUD_CLI to TEOSM_CLI", coro_06_copy_cfg_cloud_to_teosm))
    pipeline.add_step(Step("Verify TEOSM_CLI MD5", "Command & Regex verification of wigw_config.cfg MD5 on TEOSM_CLI", coro_07_verify_teosm_cfg_md5))
    pipeline.add_step(Step("Create OpenStack Image", "Run openstack image create on CLOUD_CLI & verify via Regex", coro_08_create_openstack_image))
    pipeline.add_step(Step("Run replacevars.sh", "Run echo -e '\\n1' | ./replacevars.sh on CLOUD_CLI & verify via Regex", coro_09_run_replacevars_cloud))
    pipeline.add_step(Step("Run clean.sh", "Run ./clean.sh on TEOSM_CLI & verify via Regex", coro_10_run_clean_teosm))
    pipeline.add_step(Step("Run venv.sh", "Run ./venv.sh TEOSM_INSTANCE_NAME on TEOSM_CLI & verify via Regex", coro_11_run_venv_teosm))

    pipeline.add_cleanup_step(Step("Cleanup CLOUD_NFV_FOLDER", "Delete CLOUD_NFV_FOLDER on CLOUD_CLI via command", coro_12_cleanup_cloud_folder))

    return pipeline

async def main():
    ctx = {}
    pipeline = create_launch_pipeline()
    try:
        success = await pipeline.run(ctx)
    finally:
        await coro_close_connections(ctx)
    
    if not success:
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
