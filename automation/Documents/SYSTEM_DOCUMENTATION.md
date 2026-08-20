# Automation Framework & Node Launch Pytest System Documentation

## 1. Architectural & Topology Layout

The system is a user-space, asynchronous Python network software automation suite using **Pytest** as its core test runner engine. It manages remote Linux node topologies over SSHv2 and SFTP while eliminating custom pipeline wrapper overhead in favor of native Pytest fixtures, test dependency management, and lifecycle teardown hooks.

`conftest.py` is structured as a **generic, host-decoupled wrapper library** exposing a cached configuration parser (`config_data`) and a generic SSH Connection Factory (`connect_ssh`), allowing any test case to connect to any remote node on demand. All host-specific fixture definitions and teardown cleanup hooks live directly inside the test files.

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
|  +---------------------------------------------+-----------------------------------------------+  |
|  |                            automation_framework Primitives                                  |  |
|  |  +----------------------+  +----------------------+  +-----------------------------------+  |  |
|  |  |     ConfigParser     |  |       SSHNode        |  |               Logger              |  |  |
|  |  +----------------------+  +----------------------+  +-----------------------------------+  |  |
|  +---------------------------------------------------------------------------------------------+  |
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

## 2. Component Topology & Execution Architecture

```
automation_node_launch/
├── automation_framework/     # Core low-level networking primitives
│   ├── __init__.py           # Package exports (ConfigParser, SSHNode, Logger)
│   ├── config.py             # Configuration file parser & credential extractor
│   ├── logger.py             # ANSI colored stream and file log handlers (retains ANSI color scheme in file logs)
│   └── node.py               # Asynchronous Paramiko SSHNode client & SFTP handle
├── conftest.py               # Generic wrapper library (config_data & connect_ssh factory)
├── pytest.ini                # Pytest engine options, markers, and live logging format
├── tests/
│   ├── __init__.py
│   └── test_node_launch.py   # Test suite with in-file node fixtures & teardown hooks
├── Documents/                # System documentation directory
│   ├── SYSTEM_DOCUMENTATION.md  # Main architecture & fixture design documentation
│   ├── API_DOCUMENTATION.md     # Full API specifications & schemas
│   ├── ONBOARDING_NEW_TESTS.md  # Developer guide & Pytest mechanics cheat sheet
│   └── HOW_TO_RUN_TESTS.md      # Test execution command guide
├── launch_stuffs/
│   ├── EPDGDP-1.7.0.qcow2    # Base QCOW2 virtual disk image
│   └── NFV/                  # Deployment scripts & wigw_config.cfg configuration bundle
└── variables.txt             # Host credentials and deployment paths
```

---

## 3. Generic Wrapper Fixture Architecture ([`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py))

> [!NOTE]
> For a deep-dive into Pytest engine discovery, RAM caching (`FixtureDef.cached_result`), resolution hierarchy, and factory patterns, see **[`Documents/PYTEST_FRAMEWORK_GUIDE.md`](file:///home/bikash/workera/repository/automation_node_launch/Documents/PYTEST_FRAMEWORK_GUIDE.md)**.

| Fixture Name | Scope | Description |
| :--- | :--- | :--- |
| `config_data` | `session` | Parses [`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt) **ONCE per test session** and returns cached configuration dictionary. |
| `connect_ssh` | `session` | Generic **SSH Connection Factory Wrapper**. Accepts `(connection_str, password, name="Node", timeout=600)` and returns a connected [`SSHNode`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/node.py#L8) instance for any remote host. |
| `close_ssh` | `session` | Generic **SSH Connection Teardown Wrapper**. Accepts `(node: SSHNode)` and closes active SSH and SFTP connections cleanly. |
| `test_pass` | `session` | Wrapper fixture for logging green success checkmark (`✔ SUCCESS: <msg>`). Used inside `if` branches. |
| `test_fail` | `session` | Wrapper fixture for logging red error crossmark (`✖ ERROR: <msg>`) and triggering `pytest.fail(msg)`. Used inside `else` branches. |
| `parse_credentials` | `session` | Wrapper for `ConfigParser.get_host_credentials` parsing `user@host:port`. |

---

## 4. In-File Fixtures & Teardown Mechanics ([`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py))

Node-specific fixtures and post-success cleanup hooks are defined directly inside [`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py):

- **`cloud_node`** (`module` scope): Invokes `connect_ssh(config_data["CLOUD_CLI"], config_data["CLOUD_CLI_Password"], name="CLOUD_CLI")`.
- **`teosm_node`** (`module` scope): Invokes `connect_ssh(config_data["TEOSM_CLI"], config_data["TEOSM_CLI_Password"], name="TEOSM_CLI")`.
- **`node_launch_cleanup`** (`module` scope, `autouse=True`): Teardown hook inside `test_node_launch.py` that checks `request.session.testsfailed == 0` and deletes `CLOUD_NFV_FOLDER` on `CLOUD_CLI` **only when all test steps pass**.

---

## 5. Test Execution Sequence & Fail-Fast Policy

Pytest executes tests sequentially in numerical function order inside [`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py):

```
[STEP 01] test_01_parse_variables       -> Validate required config keys
[STEP 02] test_02_verify_directories    -> Prepare CLOUD_NFV_FOLDER & check TEOSM_CLI_OPTI_FOLDER
[STEP 03] test_03_copy_stuffs_to_cloud  -> SFTP upload NFV folder & QCOW2 image to CLOUD_CLI
[STEP 04] test_04_verify_cloud_md5      -> Verify MD5 checksums on CLOUD_CLI
[STEP 05] test_05_copy_cfg_to_teosm     -> Copy wigw_config.cfg from CLOUD_CLI to TEOSM_CLI
[STEP 06] test_06_verify_teosm_cfg_md5  -> Verify wigw_config.cfg MD5 match on TEOSM_CLI
[STEP 07] test_07_create_openstack_image-> Run 'openstack image create' on CLOUD_CLI, parse UUID, sleep 60s & verify active status
[STEP 08] test_08_run_replacevars_cloud -> Run './replacevars.sh' on CLOUD_CLI, fail if volume already exists, verify new volume creation output
[STEP 09] test_09_run_clean_teosm       -> Run './clean.sh' on TEOSM_CLI
[STEP 10] test_10_edit_creds_cfg_teosm  -> Dynamically update node key & Tosca_template_path in creds.cfg on TEOSM_CLI via SFTP
[STEP 11] test_11_run_venv_teosm        -> Run './venv.sh TEOSM_INSTANCE_NAME' on TEOSM_CLI & verify VNFD + NSD upload success messages
[TEARDOWN] node_launch_cleanup (yield)  -> In-file deletion of CLOUD_NFV_FOLDER on CLOUD_CLI
```

---

## 6. Marker Filters & Command Guide

- **Run All Tests**: `pytest`
- **Run Local Offline Tests Only**: `pytest -m local`
- **Run Remote SSH Tests Only**: `pytest -m remote`
- **Run GUI Login Verification Tests**: `pytest tests/test_gui_login.py`
- **Full GUI & Tunnel Automation Guide**: See [`Documents/gui_login/SELENIUM_GUI_AUTOMATION_GUIDE.md`](file:///home/bikash/workera/personal_git/cloud-automation/automation/Documents/gui_login/SELENIUM_GUI_AUTOMATION_GUIDE.md).
- **Full Node Launch Pipeline Guide**: See [`Documents/node_launch/NODE_LAUNCH_SPECIFICATION.md`](file:///home/bikash/workera/personal_git/cloud-automation/automation/Documents/node_launch/NODE_LAUNCH_SPECIFICATION.md).
- **Full Command Guide**: See [`Documents/HOW_TO_RUN_TESTS.md`](file:///home/bikash/workera/personal_git/cloud-automation/automation/Documents/HOW_TO_RUN_TESTS.md).

---

## 7. API Specification & Code Syntax Examples

> [!NOTE]
> For full parameter listings, expected JSON schemas, SFTP operations, and code examples, see **[`Documents/API_DOCUMENTATION.md`](file:///home/bikash/workera/personal_git/cloud-automation/automation/Documents/API_DOCUMENTATION.md)**.

---

## 8. Verification Log & Test Coverage

| Test Function | Marker | Purpose & Target | Execution Command | Result |
| :--- | :--- | :--- | :--- | :--- |
| `test_01_parse_variables` | `local`, `node_launch` | Validate 9 required keys in `variables.txt` | `pytest -m local` | **PASS** |
| `test_02_verify_directories` | `remote`, `node_launch` | Verify `CLOUD_NFV_FOLDER` & `TEOSM_CLI_OPTI_FOLDER` | `pytest -m remote` | Authorized |
| `test_03_copy_stuffs_to_cloud` | `remote`, `node_launch` | SFTP upload NFV folder & QCOW2 image | `pytest -m remote` | Authorized |
| `test_04_verify_cloud_md5` | `remote`, `node_launch` | Remote `md5sum` regex match on `CLOUD_CLI` | `pytest -m remote` | Authorized |
| `test_05_copy_cfg_cloud_to_teosm` | `remote`, `node_launch` | Copy `wigw_config.cfg` from CLOUD to TEOSM | `pytest -m remote` | Authorized |
| `test_06_verify_teosm_cfg_md5` | `remote`, `node_launch` | Verify `wigw_config.cfg` MD5 on TEOSM | `pytest -m remote` | Authorized |
| `test_07_create_openstack_image` | `remote`, `node_launch` | Run `openstack image create` on `CLOUD_CLI` | `pytest -m remote` | Authorized |
| `test_08_run_replacevars_cloud` | `remote`, `node_launch` | Run `./replacevars.sh` on `CLOUD_CLI` | `pytest -m remote` | Authorized |
| `test_09_run_clean_teosm` | `remote`, `node_launch` | Run `./clean.sh` on `TEOSM_CLI` | `pytest -m remote` | Authorized |
| `test_10_run_venv_teosm` | `remote`, `node_launch` | Run `./venv.sh` on `TEOSM_CLI` | `pytest -m remote` | Authorized |
| `node_launch_cleanup` | Teardown | Post-success cleanup of `CLOUD_NFV_FOLDER` | `pytest -m local` | **PASS** |
| `test_01_verify_gui_variables` | `local`, `gui_login` | Parse & validate all GUI parameters (including `BROWSER` and `HEADLESS`) in `variables.txt` | `pytest tests/test_gui_login.py` | **PASS** |
| `test_02_verify_ssh_tunnels` | `local`, `gui_login` | Verify TCP connectivity on ports 9999 & 9998 | `pytest tests/test_gui_login.py` | **PASS** |
| `test_03_cloud_gui_login` | `local`, `gui_login` | Cloud Horizon GUI authentication via Selenium Multi-Browser Driver | `pytest tests/test_gui_login.py` | **PASS** |
| `test_04_teosm_gui_login` | `local`, `gui_login` | TEOSM GUI authentication via Selenium Multi-Browser Driver | `pytest tests/test_gui_login.py` | **PASS** |
| `test_01_verify_cleanup_variables` | `local`, `clean_teosm_gui_cloud_volume_image` | Validate cleanup parameters in `variables.txt` | `pytest -m clean_teosm_gui_cloud_volume_image tests/test_gui_cleanup.py` | **PASS** |
| `test_02_teosm_gui_login_and_cleanup` | `local`, `clean_teosm_gui_cloud_volume_image` | FIRST: TEOSM Web GUI login, breadcrumb verification, row verification, right-side Delete icon (`<i class="far fa-trash-alt icons"></i>`) click, NGB modal render (`/html/body/ngb-modal-window/div/div/app-delete`), button[2] click, notification log assertion, 60s post-instance wait, & re-search empty table check (`No data available in table`) | `pytest -m clean_teosm_gui_cloud_volume_image tests/test_gui_cleanup.py` | **PASS** |
| `test_03_cloud_cli_cleanup` | `remote`, `clean_teosm_gui_cloud_volume_image` | SECOND: Query volume info on `CLOUD_CLI` & delete volume and image via OpenStack CLI (No GUI) | `pytest -m clean_teosm_gui_cloud_volume_image tests/test_gui_cleanup.py` | **PASS** |
| `test_02_teosm_gui_launch_instance` | `local`, `launch_instance` | LAUNCH INSTANCE: Log in to TEOSM GUI, click `NS Instances`, click top-right `New NS` button, fill `Ns Name`, `Description`, select `NSD Id` & `VIM Account`, and click `Create` | `pytest -m launch_instance tests/test_gui_launch_instance.py` | **PASS** |
