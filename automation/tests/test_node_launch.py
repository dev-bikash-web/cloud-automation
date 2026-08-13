import os
import re
import glob
import time
import hashlib
import asyncio
import pytest
from typing import Generator

from automation_framework.node import SSHNode
from automation_framework.logger import log_info, test_pass, test_fail

# Macro configuration file constants
CREDS_CFG_FILE: str = "creds.cfg"

def compute_local_file_md5(path: str) -> str:
    """Helper to compute local file MD5 using hashlib."""
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

# ==============================================================================
# IN-FILE FIXTURES & TEARDOWN CLEANUP (LOCAL TO TEST FILE)
# ==============================================================================

@pytest.fixture(scope="module")
def cloud_node(connect_ssh, close_ssh, config_data: dict) -> Generator[SSHNode, None, None]:
    """In-file module fixture: Connects to CLOUD_CLI using generic conftest wrapper."""
    node = connect_ssh(
        connection_str=config_data["CLOUD_CLI"],
        password=config_data["CLOUD_CLI_Password"],
        name="CLOUD_CLI",
        timeout=600
    )
    yield node
    
    close_ssh(node)

@pytest.fixture(scope="module")
def teosm_node(connect_ssh, close_ssh, config_data: dict) -> Generator[SSHNode, None, None]:
    """In-file module fixture: Connects to TEOSM_CLI using generic conftest wrapper."""
    node = connect_ssh(
        connection_str=config_data["TEOSM_CLI"],
        password=config_data["TEOSM_CLI_Password"],
        name="TEOSM_CLI",
        timeout=600
    )
    yield node
    
    close_ssh(node)

@pytest.fixture(scope="module", autouse=False)
def node_launch_cleanup(request, cloud_node: SSHNode, config_data: dict):
    """
    In-file autouse module teardown fixture.
    Deletes CLOUD_NFV_FOLDER on CLOUD_CLI ONLY if all test steps succeeded.
    """
    yield
    
    # Check if all tests in module passed
    if hasattr(request.node, "session") and request.session.testsfailed == 0:
        cloud_folder = config_data["CLOUD_NFV_FOLDER"]
        log_info(f"[In-File Cleanup] Deleting CLOUD_NFV_FOLDER '{cloud_folder}' on CLOUD_CLI...")
        cmd = f"rm -rf '{cloud_folder}' && test ! -d '{cloud_folder}'"
        res = cloud_node.exec_and_match(cmd, regex_pattern=r"^", expect_exit_code=0)
        if res["match"]:
            test_pass(f"[In-File Cleanup] Successfully deleted CLOUD_NFV_FOLDER '{cloud_folder}'")
        else:
            test_fail(f"[In-File Cleanup] Failed to delete CLOUD_NFV_FOLDER '{cloud_folder}'")
    else:
        log_info("[In-File Cleanup] Skipping post-success cleanup due to step failure.")

# ==============================================================================
# PIPELINE TEST STEPS
# ==============================================================================

@pytest.mark.node_launch
@pytest.mark.local
def test_01_parse_variables(config_data: dict):
    """Step 1: Validate variables.txt configuration dictionary."""
    log_info("Executing Step 01: Parse variables.txt configuration...")
    required_keys = [
        "CLOUD_CLI", "CLOUD_CLI_Password",
        "TEOSM_CLI", "TEOSM_CLI_Password",
        "TEOSM_CLI_OPTI_FOLDER", "CLOUD_NFV_FOLDER",
        "IMAGE_NAME", "CFG_FILE_NAME", "TEOSM_INSTANCE_NAME"
    ]
    for key in required_keys:
        if key in config_data and config_data[key] != "":
            pass
        else:
            test_fail(f"Missing or empty required configuration key: {key}")
            
    test_pass("Step 01: variables.txt successfully parsed and validated.")

@pytest.mark.node_launch
@pytest.mark.remote
def test_02_verify_and_prepare_directories(cloud_node: SSHNode, teosm_node: SSHNode, config_data: dict):
    """Step 2: Command-based check of CLOUD_NFV_FOLDER and TEOSM_CLI_OPTI_FOLDER."""
    log_info("Executing Step 02: Verify and prepare remote directories...")
    cloud_folder = config_data["CLOUD_NFV_FOLDER"]
    teosm_folder = config_data["TEOSM_CLI_OPTI_FOLDER"]

    # 1. Check CLOUD_NFV_FOLDER on CLOUD_CLI
    res_cloud = cloud_node.exec_cmd(f"test -d '{cloud_folder}'")
    if res_cloud["exit_code"] != 0:
        log_info(f"CLOUD_NFV_FOLDER '{cloud_folder}' missing on CLOUD_CLI. Executing mkdir command...")
        res_mkdir = cloud_node.exec_and_match(
            command=f"mkdir -p '{cloud_folder}' && test -d '{cloud_folder}'",
            regex_pattern=r"^",
            expect_exit_code=0
        )
        if res_mkdir["match"]:
            test_pass(f"Created CLOUD_NFV_FOLDER '{cloud_folder}' on CLOUD_CLI.")
        else:
            test_fail(f"Failed to create CLOUD_NFV_FOLDER on CLOUD_CLI: {res_mkdir['stderr']}")
    else:
        test_pass(f"CLOUD_NFV_FOLDER '{cloud_folder}' verified on CLOUD_CLI.")

    # 2. Check TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI (Strict: fail if missing)
    res_teosm = teosm_node.exec_cmd(f"test -d '{teosm_folder}'")
    if res_teosm["exit_code"] == 0:
        test_pass(f"Verified TEOSM_CLI_OPTI_FOLDER '{teosm_folder}' exists on TEOSM_CLI.")
    else:
        test_fail(f"STRICT FAILURE: TEOSM_CLI_OPTI_FOLDER '{teosm_folder}' does NOT exist on TEOSM_CLI node!")

@pytest.mark.node_launch
@pytest.mark.remote
def test_03_copy_stuffs_to_cloud(cloud_node: SSHNode, config_data: dict):
    """Step 3: Upload NFV folder and QCOW2 image directly to CLOUD_NFV_FOLDER on CLOUD_CLI using SFTP."""
    log_info("Executing Step 03: Upload NFV folder and QCOW2 image to CLOUD_CLI...")
    cloud_folder = config_data["CLOUD_NFV_FOLDER"]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launch_stuffs_dir = os.path.join(base_dir, "launch_stuffs")

    nfv_local_dir = os.path.join(launch_stuffs_dir, "NFV")
    if not os.path.exists(nfv_local_dir):
        test_fail(f"Local NFV folder missing: {nfv_local_dir}")

    qcow2_files = glob.glob(os.path.join(launch_stuffs_dir, "*.qcow2"))
    if len(qcow2_files) == 0:
        test_fail(f"No .qcow2 files found in {launch_stuffs_dir}")
    
    qcow2_local_path = qcow2_files[0]
    qcow2_filename = os.path.basename(qcow2_local_path)
    remote_nfv_dir = os.path.join(cloud_folder, "NFV").replace('\\', '/')
    remote_qcow2_path = os.path.join(cloud_folder, qcow2_filename).replace('\\', '/')

    # Upload NFV directory via SFTP
    log_info(f"[CLOUD_CLI] SFTP Uploading directory '{nfv_local_dir}' -> '{remote_nfv_dir}'...")
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

    # Upload QCOW2 file via SFTP
    log_info(f"[CLOUD_CLI] SFTP Uploading image '{qcow2_local_path}' -> '{remote_qcow2_path}'...")
    cloud_node.sftp.put(qcow2_local_path, remote_qcow2_path)
    test_pass("Step 03: Copied NFV folder and QCOW2 file to CLOUD_CLI successfully.")

@pytest.mark.node_launch
@pytest.mark.remote
def test_04_verify_cloud_md5(cloud_node: SSHNode, config_data: dict):
    """Step 4: Execute remote md5sum command on CLOUD_CLI directly and match with local MD5."""
    log_info("Executing Step 04: Verify MD5 checksums on CLOUD_CLI...")
    cloud_folder = config_data["CLOUD_NFV_FOLDER"]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launch_stuffs_dir = os.path.join(base_dir, "launch_stuffs")

    qcow2_files = glob.glob(os.path.join(launch_stuffs_dir, "*.qcow2"))
    if len(qcow2_files) == 0:
        test_fail("No .qcow2 files found")
    qcow2_local_path = qcow2_files[0]
    qcow2_filename = os.path.basename(qcow2_local_path)
    remote_qcow2_path = os.path.join(cloud_folder, qcow2_filename).replace('\\', '/')

    local_qcow2_md5 = compute_local_file_md5(qcow2_local_path)
    cmd = f"md5sum '{remote_qcow2_path}'"
    regex_pattern = rf"^{re.escape(local_qcow2_md5)}\s+"

    res = cloud_node.exec_and_match(cmd, regex_pattern=regex_pattern)
    if not res["match"]:
        test_fail(f"MD5 MISMATCH for remote qcow2 image '{remote_qcow2_path}'. Output: {res['stdout']}")

    # Verify NFV directory files MD5
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
            file_res = cloud_node.exec_and_match(file_cmd, regex_pattern=file_regex)
            if not file_res["match"]:
                test_fail(f"MD5 MISMATCH for file '{rel_path}' on CLOUD_CLI. Output: {file_res['stdout']}")

    test_pass("Step 04: All MD5 checksums matched on CLOUD_CLI.")

@pytest.mark.node_launch
@pytest.mark.remote
def test_05_copy_cfg_cloud_to_teosm(cloud_node: SSHNode, teosm_node: SSHNode, config_data: dict, tmp_path):
    """Step 5: Copy wigw_config.cfg directly from CLOUD_CLI to TEOSM_CLI using SFTP."""
    log_info("Executing Step 05: Copy configuration file from CLOUD_CLI to TEOSM_CLI...")
    cfg_file = config_data["CFG_FILE_NAME"]
    cloud_cfg_path = os.path.join(config_data["CLOUD_NFV_FOLDER"], "NFV", cfg_file).replace('\\', '/')
    teosm_cfg_path = os.path.join(config_data["TEOSM_CLI_OPTI_FOLDER"], cfg_file).replace('\\', '/')

    temp_local_cfg = str(tmp_path / cfg_file)

    log_info(f"Downloading '{cloud_cfg_path}' from CLOUD_CLI via SFTP...")
    cloud_node.sftp.get(cloud_cfg_path, temp_local_cfg)

    log_info(f"Uploading '{cfg_file}' to TEOSM_CLI path '{teosm_cfg_path}' via SFTP...")
    teosm_node.sftp.put(temp_local_cfg, teosm_cfg_path)

    test_pass(f"Step 05: Copied {cfg_file} from CLOUD_CLI to TEOSM_CLI successfully.")

@pytest.mark.node_launch
@pytest.mark.remote
def test_06_verify_teosm_cfg_md5(cloud_node: SSHNode, teosm_node: SSHNode, config_data: dict):
    """Step 6: Execute md5sum on CLOUD_CLI & TEOSM_CLI directly and verify checksum match."""
    log_info("Executing Step 06: Verify wigw_config.cfg MD5 checksum on TEOSM_CLI...")
    cfg_file = config_data["CFG_FILE_NAME"]
    cloud_cfg_path = os.path.join(config_data["CLOUD_NFV_FOLDER"], "NFV", cfg_file).replace('\\', '/')
    teosm_cfg_path = os.path.join(config_data["TEOSM_CLI_OPTI_FOLDER"], cfg_file).replace('\\', '/')

    res_cloud = cloud_node.exec_cmd(f"md5sum '{cloud_cfg_path}'")
    cloud_match = re.search(r"^([a-fA-F0-9]{32})\s+", res_cloud["stdout"].strip())
    if not cloud_match:
        test_fail(f"Could not extract MD5 from CLOUD_CLI output: {res_cloud['stdout']}")
    cloud_md5 = cloud_match.group(1)

    teosm_cmd = f"md5sum '{teosm_cfg_path}'"
    teosm_regex = rf"^{re.escape(cloud_md5)}\s+"
    res = teosm_node.exec_and_match(teosm_cmd, regex_pattern=teosm_regex)
    if res["match"]:
        test_pass("Step 06: CFG file MD5 checksum verified on TEOSM_CLI.")
    else:
        test_fail("MD5 MISMATCH for CFG file on TEOSM_CLI!")

@pytest.mark.node_launch
@pytest.mark.remote
def test_07_create_openstack_image(cloud_node: SSHNode, config_data: dict):
    """Step 7: Create OpenStack image, extract ID, wait 1 minute, and verify active status."""
    log_info("Executing Step 07: Create OpenStack image on CLOUD_CLI...")
    cloud_folder = config_data["CLOUD_NFV_FOLDER"]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launch_stuffs_dir = os.path.join(base_dir, "launch_stuffs")

    qcow2_files = glob.glob(os.path.join(launch_stuffs_dir, "*.qcow2"))
    if len(qcow2_files) == 0:
        test_fail("No .qcow2 files found")
    qcow2_filename = os.path.basename(qcow2_files[0])
    qcow2_path = os.path.join(cloud_folder, qcow2_filename).replace('\\', '/')
    image_name = config_data["IMAGE_NAME"]

    # 1. Run OpenStack Image Create command
    cmd_create = f"openstack image create '{image_name}' --disk-format qcow2 --file '{qcow2_path}' --public"
    res_create = cloud_node.exec_cmd(cmd_create, timeout=900)
    
    if res_create["exit_code"] != 0:
        test_fail(f"OpenStack Image Creation Failed! STDOUT: {res_create['stdout']}\nSTDERR: {res_create['stderr']}")

    # 2. Extract Image ID using Regex from ASCII Table output
    id_match = re.search(r"\|\s*id\s*\|\s*([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\s*\|", res_create["stdout"], re.IGNORECASE)
    if not id_match:
        test_fail(f"Could not extract Image ID from openstack output!\nOutput was:\n{res_create['stdout']}")

    image_id = id_match.group(1)
    log_info(f"OpenStack Image created with ID: '{image_id}'. Waiting 60 seconds (1 minute) for status check...")

    # 3. Wait 1 minute for output processing
    time.sleep(60)

    # 4. Check status using openstack image show <image_id>
    cmd_show = f"openstack image show '{image_id}'"
    res_show = cloud_node.exec_and_match(cmd_show, regex_pattern=r"\|\s*status\s*\|\s*active\s*\|")

    if res_show["match"]:
        test_pass(f"Step 07: OpenStack Image '{image_name}' (ID: {image_id}) is active.")
    else:
        test_fail(f"OpenStack Image '{image_id}' status check failed! Image is not active.\nOutput:\n{res_show['stdout']}")

@pytest.mark.node_launch
@pytest.mark.remote
def test_08_run_replacevars_cloud(cloud_node: SSHNode, config_data: dict):
    """Step 8: Execute './replacevars.sh' on CLOUD_CLI and verify volume creation output."""
    log_info("Executing Step 08: Run replacevars.sh on CLOUD_CLI...")
    nfv_remote_dir = os.path.join(config_data["CLOUD_NFV_FOLDER"], "NFV").replace('\\', '/')
    cmd = "chmod +x ./replacevars.sh && echo -e \"\\n1\" | ./replacevars.sh"

    res = cloud_node.exec_cmd(cmd, cwd=nfv_remote_dir, pty=True, timeout=600)
    
    if res["exit_code"] != 0:
        test_fail(f"replacevars.sh execution failed with exit code {res['exit_code']}!\nOutput:\n{res['stdout']}")

    output = res["stdout"] + ("\n" + res["stderr"] if res["stderr"] else "")

    # 1. Check for Pre-Existing Volume Failure (Must fail if volume already exists)
    if re.search(r"(already created.*skipping creation|Volume.*already created)", output, re.IGNORECASE):
        test_fail(f"replacevars.sh FAILED: Volume already exists on CLOUD_CLI! Skipping creation detected.\nOutput:\n{output}")

    # 2. Check for Successful Volume Creation
    regex_success = r"(Creating CFW Node.*volume|Writing .* in .*volume_check\.cfg|\|\s*status\s*\|\s*creating\s*\|)"
    if re.search(regex_success, output, re.IGNORECASE):
        test_pass("Step 08: replacevars.sh executed successfully and created new volume.")
    else:
        test_fail(f"replacevars.sh output did not match expected volume creation pattern!\nOutput:\n{output}")

@pytest.mark.node_launch
@pytest.mark.remote
def test_09_run_clean_teosm(teosm_node: SSHNode, config_data: dict):
    """Step 9: Execute './clean.sh' in TEOSM_CLI_OPTI_FOLDER on TEOSM_CLI directly."""
    log_info("Executing Step 09: Run clean.sh on TEOSM_CLI...")
    opti_folder = config_data["TEOSM_CLI_OPTI_FOLDER"]
    cmd = "chmod +x ./clean.sh && ./clean.sh"

    res = teosm_node.exec_and_match(cmd, regex_pattern=r".+", cwd=opti_folder, pty=True)
    if res["match"]:
        test_pass("Step 09: clean.sh executed successfully on TEOSM_CLI.")
    else:
        test_fail("clean.sh execution failed on TEOSM_CLI!")

@pytest.mark.node_launch
@pytest.mark.remote
def test_10_edit_creds_cfg_teosm(teosm_node: SSHNode, config_data: dict):
    """Step 10: Dynamically update node key & Tosca_template_path in creds.cfg on TEOSM_CLI via SFTP."""
    log_info(f"Executing Step 10: Dynamically edit {CREDS_CFG_FILE} on TEOSM_CLI...")
    opti_folder = config_data["TEOSM_CLI_OPTI_FOLDER"]
    instance_name = config_data["TEOSM_INSTANCE_NAME"]
    cloud_folder = config_data["CLOUD_NFV_FOLDER"]
    tosca_path = os.path.join(cloud_folder, "NFV", "generated_vnf_ns").replace('\\', '/')
    remote_creds_path = os.path.join(opti_folder, CREDS_CFG_FILE).replace('\\', '/')

    # 1. Read creds.cfg from TEOSM_CLI via SFTP
    try:
        with teosm_node.sftp.open(remote_creds_path, 'r') as f:
            text = f.read().decode('utf-8')
    except Exception as e:
        test_fail(f"Failed to read '{remote_creds_path}' via SFTP from TEOSM_CLI: {e}")

    # 2. Backup creds.cfg on TEOSM_CLI
    teosm_node.exec_cmd(f"cp '{remote_creds_path}' '{remote_creds_path}.bak'", cwd=opti_folder)

    # 3. Update Tosca_template_path in creds.cfg
    text = re.sub(
        r"(^\s*Tosca_template_path\s*=).*",
        rf"\1 {tosca_path}",
        text,
        flags=re.MULTILINE
    )

    # 4. Dynamically find the old node key in Template_files or NSD_Segregation
    m = re.search(r"Template_files\s*=\s*\{\s*\"([^\"]+)\"\s*:", text)
    if not m:
        m = re.search(r"NSD_Segregation\s*=[\s\S]*?\[\s*\"([^\"]+)\"", text)

    if not m:
        test_fail(f"Could not find active node key in '{CREDS_CFG_FILE}' on TEOSM_CLI!")

    old_key = m.group(1)
    new_text = text.replace(f'"{old_key}"', f'"{instance_name}"')

    # 5. Write updated creds.cfg back to TEOSM_CLI via SFTP
    try:
        with teosm_node.sftp.open(remote_creds_path, 'w') as f:
            f.write(new_text)
        log_info(f"Updated {CREDS_CFG_FILE}: Tosca_template_path -> '{tosca_path}', node key '{old_key}' -> '{instance_name}'")
    except Exception as e:
        test_fail(f"Failed to write updated '{remote_creds_path}' via SFTP to TEOSM_CLI: {e}")

    # 6. Verify replacements via grep on TEOSM_CLI
    cmd_verify_key = f"grep -i '\"{instance_name}\"' {CREDS_CFG_FILE}"
    cmd_verify_path = f"grep -i '{tosca_path}' {CREDS_CFG_FILE}"
    
    res_key = teosm_node.exec_and_match(cmd_verify_key, regex_pattern=rf"\"{re.escape(instance_name)}\"", cwd=opti_folder)
    res_path = teosm_node.exec_and_match(cmd_verify_path, regex_pattern=re.escape(tosca_path), cwd=opti_folder)

    if res_key["match"] and res_path["match"]:
        test_pass(f"Step 10: Successfully updated node key and Tosca_template_path in {CREDS_CFG_FILE} on TEOSM_CLI.")
    else:
        test_fail(f"Verification failed! '{instance_name}' or '{tosca_path}' not found in {CREDS_CFG_FILE} on TEOSM_CLI.")

@pytest.mark.node_launch
@pytest.mark.remote
def test_11_run_venv_teosm(teosm_node: SSHNode, config_data: dict):
    """Step 11: Execute './venv.sh TEOSM_INSTANCE_NAME' in TEOSM_CLI_OPTI_FOLDER and verify VNFD & NSD uploads."""
    log_info("Executing Step 11: Run venv.sh on TEOSM_CLI...")
    opti_folder = config_data["TEOSM_CLI_OPTI_FOLDER"]
    instance_name = config_data["TEOSM_INSTANCE_NAME"]
    cmd = f"chmod +x ./venv.sh && ./venv.sh '{instance_name}'"

    # Regex strictly verifies both VNFD and NSD package upload confirmation messages
    regex_pattern = r".*_vnf\.tar\.gz\s+Uploaded\s+successfully[\s\S]*.*_nsd\.tar\.gz\s+Uploaded\s+successfully"

    res = teosm_node.exec_and_match(cmd, regex_pattern=regex_pattern, cwd=opti_folder, pty=True, timeout=600)
    if res["match"]:
        test_pass("Step 11: venv.sh executed successfully and uploaded both VNFD and NSD packages to OSM.")
    else:
        test_fail("Step 11 FAILED: venv.sh execution failed or package upload confirmations missing.")
