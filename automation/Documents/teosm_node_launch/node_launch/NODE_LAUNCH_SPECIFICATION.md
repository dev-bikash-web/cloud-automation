# Node Launch Pipeline Test Specification Guide

## 1. Architectural & Topology Layout

The **Node Launch Pipeline Component** automates end-to-end VNF/CNF node provisioning across Cloud (`CLOUD_CLI`) and TEOSM (`TEOSM_CLI`) infrastructure over SSHv2 and SFTP.

```
+---------------------------------------------------------------------------------------------------+
|                                      Local Controller Host                                        |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |             conftest.py (Generic Wrappers: config_data & connect_ssh Factory)               |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                |                                                  |
|  +---------------------------------------------+-----------------------------------------------+  |
|  |             tests/test_node_launch.py (In-File Fixtures & Teardown Cleanup)                 |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  |  | test_01_parse_config|  | test_02_verify_dirs     |  | test_03_copy_stuffs_to_cloud    |  |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  |  | test_04_verify_md5  |  | test_05_copy_cfg        |  | test_06_verify_teosm_md5        |  |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  |  | test_07_openstack   |  | test_08_replacevars     |  | test_09_clean & test_10_venv    |  |  |
|  |  +---------------------+  +-------------------------+  +---------------------------------+  |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                |                                                  |
+------------------------------------------------|--------------------------------------------------+
                                                 |
                       +-------------------------+-------------------------+
                       | SSHv2 (Port 22) / SFTP                            | SSHv2 (Port 22) / SFTP
                       v                                                   v
+--------------------------------------+                   +--------------------------------------+
|       CLOUD_CLI Remote Node          |                   |        TEOSM_CLI Remote Node         |
|            (172.23.1.50)             |                   |            (172.23.9.10)             |
|                                      |                   |                                      |
| - Command Exec & Regex Match         | -- SFTP Transfer->| - Command Exec & Regex Match         |
| - CLOUD_NFV_FOLDER/                  |  (wigw_config.cfg)| - TEOSM_CLI_OPTI_FOLDER/             |
|   - NFV/ (replacevars.sh)            |                   |   - clean.sh / venv.sh               |
|   - *.qcow2 image                    |                   |                                      |
| - OpenStack Image Creation           |                   |                                      |
+--------------------------------------+                   +--------------------------------------+
```

---

## 2. Test Pipeline Execution Steps (`test_node_launch.py`)

1. **Step 01 (`test_01_parse_variables`)**: Validate required variables in `variables.txt`.
2. **Step 02 (`test_02_verify_directories`)**: Create and verify remote NFV and optimization folders on `CLOUD_CLI` and `TEOSM_CLI`.
3. **Step 03 (`test_03_copy_stuffs_to_cloud`)**: SFTP upload local NFV directory & QCOW2 image to `CLOUD_CLI`.
4. **Step 04 (`test_04_verify_cloud_md5`)**: Compute local vs remote MD5 checksums.
5. **Step 05 (`test_05_copy_cfg_cloud_to_teosm`)**: Transfer configuration file from `CLOUD_CLI` to `TEOSM_CLI`.
6. **Step 06 (`test_06_verify_teosm_cfg_md5`)**: Verify MD5 checksum on `TEOSM_CLI`.
7. **Step 07 (`test_07_create_openstack_image`)**: Execute `openstack image create` on `CLOUD_CLI` and verify `active` state.
8. **Step 08 (`test_08_run_replacevars_cloud`)**: Run `./replacevars.sh` on `CLOUD_CLI` and verify volume creation.
9. **Step 09 (`test_09_run_clean_teosm`)**: Run `./clean.sh` on `TEOSM_CLI`.
10. **Step 10 (`test_10_edit_creds_cfg_teosm`)**: Update `creds.cfg` parameters via SFTP on `TEOSM_CLI`.
11. **Step 11 (`test_11_run_venv_teosm`)**: Execute `./venv.sh` on `TEOSM_CLI` and verify OSM package upload.
