# Selenium GUI Automation & SSH Tunnel Specification Guide

## 1. Architectural & Topology Layout

The **Selenium GUI Automation Component** extends the Pytest test suite to perform upfront SSH port-forwarding tunnel establishment and automated web GUI authentication for Cloud (OpenStack Horizon) and TEOSM management systems.

### 1.1 Runtime Topology Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                      Local Controller Host                                        |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                 conftest.py (Provides config_data fixture parsing variables.txt)             |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                |                                                  |
|  +---------------------------------------------+-----------------------------------------------+  |
|  |                            tests/test_gui_login.py                                         |  |
|  |                                                                                             |  |
|  |  +----------------------------------+     +----------------------------------------------+  |  |
|  |  |   gui_tunnels (Module Fixture)   |     |    browser_driver (Function Fixture)         |  |  |
|  |  |   - Spawns background sshpass    |     |    - Multi-browser factory (Firefox/Chrome)  |  |  |
|  |  |     tunnels on ports 9999 & 9998 |     |    - Toggles Headless vs Visible Window Mode |  |  |
|  |  +----------------------------------+     +----------------------------------------------+  |  |
|  |                                             |                                                  |  |
|  |  +---------------------+  +---------------------+  +-------------------+  +------------------+  |  |
|  |  | test_01_verify_vars |  | test_02_verify_ports|  | test_03_cloud_gui |  | test_04_teosm_gui|  |  |
|  |  +---------------------+  +---------------------+  +-------------------+  +------------------+  |  |
|  +---------------------------------------------------------------------------------------------+  |
|         │                                 │                                    │                  |
+---------│---------------------------------│------------------------------------│------------------+
          │ TCP Tunnel (Port 9999)          │ TCP Tunnel (Port 9998)             │ W3C WebDriver IPC
          v                                 v                                    v
+-----------------------+         +-----------------------+           +-----------------------+
|  CLOUD_GUI Endpoint   |         |  TEOSM_GUI Endpoint   |           | Firefox / Chrome      |
|  172.23.1.10:80       |         |  172.23.9.10:32000    |           | Selenium Engine       |
|  (OpenStack Horizon)  |         |  (TEOSM Web Portal)   |           | (Headless / Visual)   |
+-----------------------+         +-----------------------+           +-----------------------+
```

---

## 2. Configuration & Protocol Specification

### 2.1 Parameter Specification (`variables.txt`)

All GUI and SSH tunnel configuration parameters are loaded dynamically via the `config_data` fixture from [`automation/variables.txt`](file:///home/bikash/workera/personal_git/cloud-automation/automation/variables.txt):

| Parameter Key | Format / Example Value | Description |
| :--- | :--- | :--- |
| `CLOUD_GUI` | `ssh -L 9999:172.23.1.10:80 cdot@192.168.129.40` | SSH port-forwarding command string for OpenStack Horizon. |
| `TEOSM_GUI` | `ssh -L 9998:172.23.9.10:32000 cdot@192.168.129.40` | SSH port-forwarding command string for TEOSM Web Portal. |
| `GUI_CLI_PASS` | `Val@1984$` | Password for SSH jump host authentication. |
| `CLOUD_GUI_URL` | `http://localhost:9999/horizon/auth/login/` | Local URL endpoint for Cloud Horizon GUI. |
| `TEOSM_GUI_URL` | `https://localhost:9998/login` | Local URL endpoint for TEOSM Web Portal. |
| `CLOUD_GUI_USER_NAME` | `admin` | Username for OpenStack Horizon authentication. |
| `CLOUD_GUI_USER_PASS` | `CloudPRGR@123` | Password for OpenStack Horizon authentication. |
| `COULD_DOMAIN` | `default` | Domain identifier for OpenStack Horizon authentication. |
| `TEOSM_GUI_USER_NAME` | `admin` | Username for TEOSM Web Portal authentication. |
| `TEOSM_GUI_USER_PASS` | `admin` | Password for TEOSM Web Portal authentication. |
| `HEADLESS` | `false` | `false` launches visible browser on display; `true` runs headlessly. |
| `BROWSER` | `firefox` | Selected browser driver (`firefox`, `chrome`, `edge`, `chromium`). |

---

## 3. Multi-Browser Factory & Driver Capabilities

The browser driver engine is constructed dynamically by the `browser_driver` fixture in [`automation/tests/test_gui_login.py`](file:///home/bikash/workera/personal_git/cloud-automation/automation/tests/test_gui_login.py):

```python
def create_browser_driver(browser_name: str, headless: bool = False) -> webdriver.Remote:
    ...
```

### 3.1 Supported Browsers & Fallback Behavior

1. **Firefox (`BROWSER=firefox`)**:
   - Uses `FirefoxOptions()`.
   - Bypasses untrusted TLS certificates (`options.accept_insecure_certs = True`).
   - Automatically searches for Snap and system Firefox binary candidates (`/snap/firefox/current/usr/lib/firefox/firefox`, `/usr/bin/firefox`).
2. **Chrome / Chromium (`BROWSER=chrome` / `BROWSER=chromium`)**:
   - Uses `ChromeOptions()` with `--no-sandbox`, `--disable-dev-shm-usage`, and `--disable-gpu`.
   - Supports `--headless=new` mode.
3. **Microsoft Edge (`BROWSER=edge`)**:
   - Uses `EdgeOptions()`.
4. **Driver Fallback Safeguard**:
   - If `BROWSER=chrome` or `BROWSER=edge` is configured but the system lacks the specific driver binary, the factory logs a warning and automatically falls back to the system's available Firefox driver.

---

## 4. Test Suite Specification (`test_gui_login.py`)

The test suite consists of 4 sequential steps tagged with `@pytest.mark.gui_login` and `@pytest.mark.local`:

```
[STEP 01] test_01_verify_gui_variables -> Validates presence of all 11 required keys in variables.txt
[STEP 02] test_02_verify_ssh_tunnels   -> Probes TCP sockets on local ports 9999 and 9998
[STEP 03] test_03_cloud_gui_login      -> Performs OpenStack Horizon authentication via Selenium
[STEP 04] test_04_teosm_gui_login      -> Performs TEOSM Web Portal authentication via Selenium
[TEARDOWN] gui_tunnels / browser_driver -> Quits browser driver & terminates SSH tunnel PIDs
```

### 4.1 Form Interaction Locators

- **Cloud (Horizon) GUI**:
  - Domain locator: `By.NAME, "domain"` or `By.ID, "id_domain"`
  - Username locator: `By.NAME, "username"` or `By.ID, "id_username"`
  - Password locator: `By.NAME, "password"` or `By.ID, "id_password"`
  - Submit button locator: `By.ID, "submit-login"` or `XPath: //button[@type='submit']`
- **TEOSM GUI**:
  - Username locator: `By.NAME, "username"` or `By.ID, "username"` or `XPath: //input[@type='text']`
  - Password locator: `By.NAME, "password"` or `By.ID, "password"` or `XPath: //input[@type='password']`
  - Submit button locator: `XPath: //button[@type='submit']` or `form.submit()`

---

## 5. Performance & Operational Profile

| Metric / Resource | Baseline Profile | Configuration Tuning |
| :--- | :--- | :--- |
| **Total Test Execution Time** | ~68 seconds | Includes 15s element timeouts & post-submit sleep buffers |
| **Firefox Driver Memory Footprint** | ~180 MB - 250 MB | Closed immediately during fixture teardown (`driver.quit()`) |
| **SSH Tunnel CPU Utilization** | < 0.1% | Non-blocking `subprocess.Popen` with `-N` (no command execution) |
| **TCP Socket Polling Timeout** | 15 seconds max | Socket probe checks `127.0.0.1:9999` and `127.0.0.1:9998` |
| **Log Routing Target** | `test_gui_login_execution.log` | Managed by framework `DynamicFileHandler` |

---

## 6. Verification Log & Test Coverage

### 6.1 Test Coverage Results

| Test Function | Markers | Target / Verification | Command | Result |
| :--- | :--- | :--- | :--- | :--- |
| `test_01_verify_gui_variables` | `gui_login`, `local` | Validate 11 GUI & driver variables | `pytest tests/test_gui_login.py` | **PASS** |
| `test_02_verify_ssh_tunnels` | `gui_login`, `local` | Verify TCP sockets on ports 9999 & 9998 | `pytest tests/test_gui_login.py` | **PASS** |
| `test_03_cloud_gui_login` | `gui_login`, `local` | Horizon GUI login & redirect check | `pytest tests/test_gui_login.py` | **PASS** |
| `test_04_teosm_gui_login` | `gui_login`, `local` | TEOSM GUI login & redirect check | `pytest tests/test_gui_login.py` | **PASS** |
| `gui_tunnels` (Teardown) | Module Fixture | Terminate background SSH tunnel PIDs | `pytest tests/test_gui_login.py` | **PASS** |
| `browser_driver` (Teardown) | Function Fixture | Quit Selenium WebDriver processes | `pytest tests/test_gui_login.py` | **PASS** |

### 6.2 Sample Passing Execution Output

```text
====================== AUTOMATION SUITE EXECUTION SUMMARY ======================
✔ SUCCESS: All 4 test case(s) passed for marker 'all'!
=======================================  =======================================
=================== 4 passed, 4 warnings in 68.65s (0:01:08) ===================
```

---

## 7. How to Run the GUI Test Suite

Execute the GUI login test suite using standard pytest:

```bash
# Run GUI Login test suite directly
pytest tests/test_gui_login.py

# Run with verbose live console logs
pytest tests/test_gui_login.py -o log_cli=true

# Filter tests by keyword
pytest -k gui_login
```
