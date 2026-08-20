# Test Execution Guide: Running the Pytest Automation Suite

This guide provides comprehensive instructions on how to execute, filter, debug, and troubleshoot test cases in the Pytest Network Automation framework.

---

## 1. Quick Command Summary

| Goal | Command | Description |
| :--- | :--- | :--- |
| **Run All Tests** | `pytest` | Discovers and executes all test cases in the [`tests/`](file:///home/bikash/workera/repository/automation_node_launch/tests) directory. |
| **Run Local Tests Only** | `pytest -m local` | Executes offline unit tests locally on the controller host without initiating SSH connections. |
| **Run Remote SSH Tests** | `pytest -m remote` | Executes test cases against remote `CLOUD_CLI` (172.23.1.50) and `TEOSM_CLI` (172.23.9.10) nodes over SSHv2. |
| **Run Node Launch Suite** | `pytest -m node_launch` | Executes the complete end-to-end Node Launch pipeline suite. |
| **Run Specific Test File** | `pytest tests/test_node_launch.py` | Executes only the specified test module. |
| **Run GUI Login Test Suite** | `pytest tests/test_gui_login.py` | Executes upfront SSH tunnel creation and Firefox/Chrome GUI logins. |
| **Run Specific Test Case** | `pytest -k "test_01_parse_variables"` | Runs test functions matching a keyword pattern. |
| **Verbose Live Log Run** | `pytest -vs` | Displays real-time console prints and full verbose test names. |

---

## 2. Prerequisites & Setup

1. **Verify Python & Pytest Installation**:
   Ensure Python 3.8+ and `pytest` are installed on your controller host:
   ```bash
   python3 -m pytest --version
   ```

2. **Verify Configuration ([`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt))**:
   Ensure [`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt) contains target host credentials and folder paths:
   ```ini
   CLOUD_CLI=cdot@172.23.1.50
   CLOUD_CLI_Password=Cdot@1234
   TEOSM_CLI=bsnladmin@172.23.9.10
   TEOSM_CLI_Password=bsnl@123
   TEOSM_CLI_OPTI_FOLDER=/home/bsnladmin/optimized_pycscript_EPDGDP_patch6_teosm8x/EPDGDP_3.1.0_MultipleInterface_Patch6_teosm8x
   CLOUD_NFV_FOLDER=/home/cdot/CFW/test
   IMAGE_NAME=EPDGDP-3.3.0
   CFG_FILE_NAME=wigw_config.cfg
   TEOSM_INSTANCE_NAME=epdg_dp_node1
   ```

---

## 3. Step-by-Step Test Execution Scenarios

### Scenario A: Running Local Offline Unit Tests (Safe Offline Test)
Use this command to quickly verify configuration syntax and local logic without needing network access to remote nodes:

```bash
pytest -m local
```
*Expected Output*:
```
tests/test_node_launch.py::test_01_parse_variables PASSED [100%]
=================== 1 passed, 9 deselected in 0.95s ===================
```

---

### Scenario B: Running Remote SSH Node Launch Tests
Use this command to execute tests that interact with live remote nodes over SSHv2 and SFTP:

```bash
pytest -m remote
```

---

### Scenario C: Running the Full Suite with Real-Time Live Logs
To see real-time progress logs (`log_info`, `log_success`, `log_error`) as each step executes:

```bash
pytest -vs
```

---

### Scenario D: Running a Single Test Step for Fast Debugging
If a specific step failed (e.g., `test_04_verify_cloud_md5`), run only that test function:

```bash
pytest -k "test_04_verify_cloud_md5" -vs
```

---

## 4. Understanding Pytest Execution Controls (`pytest.ini`)

The test suite defaults are preconfigured in [`pytest.ini`](file:///home/bikash/workera/repository/automation_node_launch/pytest.ini):

- **Fail-Fast Policy (`--maxfail=1`)**: Halts execution immediately if any step fails, preventing cascading errors on remote nodes.
- **Short Tracebacks (`--tb=short`)**: Displays concise, readable error tracebacks focused on the exact line of code that failed.
- **Live Terminal Logging (`log_cli = true`)**: Stream-logs formatted informational output (`YYYY-MM-DD HH:MM:SS [INFO] ...`) during test runs.

---

## 5. Troubleshooting Common Issues

### Issue 1: `Missing required configuration key in variables.txt`
- **Cause**: One of the required credentials or folder paths is missing in `variables.txt`.
- **Fix**: Check `variables.txt` and ensure all required keys are defined.

### Issue 2: `Authentication (password) failed` or `TimeoutError`
- **Cause**: Invalid SSH password or remote host IP address unreachable.
- **Fix**: Verify host ping connectivity (`ping 172.23.1.50`) and test SSH login manually (`ssh cdot@172.23.1.50`).

### Issue 3: `STRICT FAILURE: TEOSM_CLI_OPTI_FOLDER does NOT exist`
- **Cause**: Mandatory optimization directory is missing on `TEOSM_CLI`.
- **Fix**: Verify that the folder path in `TEOSM_CLI_OPTI_FOLDER` exists on `TEOSM_CLI` before running tests.
