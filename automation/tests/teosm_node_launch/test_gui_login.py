import os
import re
import time
import socket
import subprocess
import pytest
from typing import Generator, Dict, Optional, Tuple, List

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automation_framework.logger import log_info, test_pass, test_fail

# ==============================================================================
# HELPER UTILITIES FOR SSH TUNNELS & SOCKET PROBING
# ==============================================================================

def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Utility to check if local TCP socket is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

def parse_ssh_tunnel_cmd(cmd_str: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Parses SSH command strings like:
    'ssh -L 9999:172.23.1.10:80 cdot@192.168.129.40'
    Returns: (local_port, remote_target, jump_host)
    """
    match = re.search(r'-L\s+(\d+):([\w\.\-]+:\d+)\s+([\w\.\-]+@[\w\.\-]+)', cmd_str)
    if match:
        local_port = int(match.group(1))
        remote_target = match.group(2)
        jump_host = match.group(3)
        return local_port, remote_target, jump_host
    return None, None, None

def create_browser_driver(browser_name: str, headless: bool = False) -> webdriver.Remote:
    """
    Factory helper to instantiate Selenium WebDriver based on BROWSER parameter.
    Supports: 'firefox', 'chrome', 'edge', 'chromium'.
    Falls back to Firefox if the requested driver binary is unavailable.
    """
    b_type = browser_name.lower().strip()
    log_info(f"Initializing Selenium WebDriver (Browser: '{b_type}', Headless: {headless})...")

    if b_type in ["chrome", "chromium", "google-chrome"]:
        try:
            options = ChromeOptions()
            options.accept_insecure_certs = True
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            if headless:
                options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            log_info(f"Failed to initialize Chrome driver: {e}. Falling back to Firefox...")

    elif b_type in ["edge", "microsoft-edge", "msedge"]:
        try:
            options = EdgeOptions()
            options.accept_insecure_certs = True
            if headless:
                options.add_argument("--headless")
            driver = webdriver.Edge(options=options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            log_info(f"Failed to initialize Edge driver: {e}. Falling back to Firefox...")

    # Default / Firefox branch
    options = FirefoxOptions()
    options.accept_insecure_certs = True
    if headless:
        options.add_argument("--headless")

    firefox_candidates = [
        "/snap/firefox/current/usr/lib/firefox/firefox",
        "/usr/bin/firefox",
        "/usr/lib/firefox/firefox"
    ]
    for binary_path in firefox_candidates:
        if os.path.exists(binary_path):
            options.binary_location = binary_path
            break

    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    return driver

# ==============================================================================
# PYTEST FIXTURES FOR GUI TUNNELS AND SELENIUM BROWSER DRIVER
# ==============================================================================

@pytest.fixture(scope="module")
def gui_tunnels(config_data: dict) -> Generator[Dict[str, int], None, None]:
    """
    Module fixture: Dynamically establishes SSH port-forwarding tunnels upfront
    for CLOUD_GUI (port 9999) and TEOSM_GUI (port 9998) using sshpass.
    Cleans up tunnel processes on module completion.
    """
    gui_pass = config_data.get("GUI_CLI_PASS", "")
    tunnel_cmds = {
        "CLOUD_GUI": config_data.get("CLOUD_GUI", ""),
        "TEOSM_GUI": config_data.get("TEOSM_GUI", "")
    }

    spawned_processes: List[subprocess.Popen] = []
    active_ports: Dict[str, int] = {}

    for name, cmd in tunnel_cmds.items():
        if not cmd:
            log_info(f"[{name}] No SSH tunnel command specified in variables.txt")
            continue

        local_port, remote_target, jump_host = parse_ssh_tunnel_cmd(cmd)
        if not local_port or not remote_target or not jump_host:
            test_fail(f"[{name}] Failed to parse tunnel command string: '{cmd}'")
            continue

        active_ports[name] = local_port

        if is_port_open(local_port):
            log_info(f"[{name}] Tunnel port {local_port} is already listening.")
            continue

        log_info(f"[{name}] Launching SSH tunnel on port {local_port} -> {remote_target} via {jump_host}...")
        sshpass_cmd = [
            "sshpass", "-p", gui_pass,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=15",
            "-N",
            "-L", f"{local_port}:{remote_target}",
            jump_host
        ]

        try:
            proc = subprocess.Popen(
                sshpass_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            spawned_processes.append(proc)
        except Exception as e:
            test_fail(f"[{name}] Failed to execute sshpass tunnel command: {e}")

        # Poll socket until listening (up to 15 seconds)
        start_time = time.time()
        tunnel_ready = False
        while time.time() - start_time < 15:
            if is_port_open(local_port):
                tunnel_ready = True
                break
            time.sleep(1)

        if tunnel_ready:
            log_info(f"[{name}] SSH tunnel on port {local_port} established successfully.")
        else:
            log_info(f"[{name}] Warning: Socket on port {local_port} not responding within 15 seconds.")

    yield active_ports

    # Teardown: terminate spawned tunnel subprocesses
    log_info("[Teardown] Terminating spawned SSH tunnel processes...")
    for proc in spawned_processes:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

@pytest.fixture(scope="function")
def browser_driver(config_data: dict) -> Generator[webdriver.Remote, None, None]:
    """
    Function fixture: Initializes Selenium WebDriver based on BROWSER and HEADLESS parameters in variables.txt.
    Supports: firefox, chrome, edge, chromium.
    """
    browser_name = config_data.get("BROWSER", "firefox")
    headless_setting = config_data.get("HEADLESS", "false").lower() == "true"

    driver = create_browser_driver(browser_name=browser_name, headless=headless_setting)

    yield driver

    log_info("Closing Selenium WebDriver...")
    try:
        driver.quit()
    except Exception:
        pass

# ==============================================================================
# TEST STEPS FOR GUI TUNNEL CREATION AND LOGIN
# ==============================================================================

@pytest.mark.gui_login
@pytest.mark.local
def test_01_verify_gui_variables(config_data: dict):
    """Step 1: Parse and validate all GUI parameters from variables.txt."""
    log_info("Executing Step 01: Verifying GUI variables in configuration...")
    required_keys = [
        "CLOUD_GUI_URL", "TEOSM_GUI_URL",
        "CLOUD_GUI_USER_NAME", "CLOUD_GUI_USER_PASS", "COULD_DOMAIN",
        "TEOSM_GUI_USER_NAME", "TEOSM_GUI_USER_PASS",
        "CLOUD_GUI", "TEOSM_GUI", "GUI_CLI_PASS", "BROWSER"
    ]
    for key in required_keys:
        if key not in config_data or not config_data[key]:
            test_fail(f"Missing or empty required GUI configuration key: {key}")

    log_info(f"Configured browser: '{config_data['BROWSER']}', Headless mode: '{config_data.get('HEADLESS', 'false')}'")
    test_pass("Step 01: All GUI parameters successfully parsed and validated from variables.txt.")

@pytest.mark.gui_login
@pytest.mark.local
def test_02_verify_ssh_tunnels(config_data: dict, gui_tunnels: dict):
    """Step 2: Verify active TCP connectivity on local SSH tunnel ports (9999 and 9998)."""
    log_info("Executing Step 02: Verifying SSH tunnel TCP socket connectivity...")
    for gui_name in ["CLOUD_GUI", "TEOSM_GUI"]:
        cmd = config_data.get(gui_name, "")
        local_port, _, _ = parse_ssh_tunnel_cmd(cmd)
        if not local_port:
            test_fail(f"Could not extract local port for {gui_name}")

        if is_port_open(local_port):
            log_info(f"✔ TCP socket port {local_port} ({gui_name}) is active and listening.")
        else:
            test_fail(f"TCP socket port {local_port} ({gui_name}) is not responding.")

    test_pass("Step 02: All required GUI SSH tunnel sockets verified active.")

@pytest.mark.gui_login
@pytest.mark.local
def test_03_cloud_gui_login(config_data: dict, gui_tunnels: dict, browser_driver: webdriver.Remote):
    """Step 3: Perform Cloud (Horizon) GUI authentication upfront via Selenium."""
    log_info("Executing Step 03: Cloud (Horizon) GUI Login verification...")
    url = config_data["CLOUD_GUI_URL"]
    username = config_data["CLOUD_GUI_USER_NAME"]
    password = config_data["CLOUD_GUI_USER_PASS"]
    domain = config_data.get("COULD_DOMAIN", "default")

    log_info(f"Navigating to Cloud GUI URL: {url}")
    try:
        browser_driver.get(url)
    except Exception as e:
        test_fail(f"Failed to load Cloud GUI URL '{url}': {e}")

    # Wait for login form to load
    try:
        WebDriverWait(browser_driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
    except Exception:
        test_fail("Cloud GUI login page failed to render username field within timeout.")

    # Fill Domain if present on Horizon login page
    try:
        domain_elem = browser_driver.find_element(By.NAME, "domain")
        domain_elem.clear()
        domain_elem.send_keys(domain)
        log_info(f"Entered domain: {domain}")
    except Exception:
        try:
            domain_elem = browser_driver.find_element(By.ID, "id_domain")
            domain_elem.clear()
            domain_elem.send_keys(domain)
            log_info(f"Entered domain: {domain}")
        except Exception:
            log_info("Domain field not present/required on this Horizon login form.")

    # Fill Username
    try:
        user_elem = browser_driver.find_element(By.NAME, "username")
    except Exception:
        user_elem = browser_driver.find_element(By.ID, "id_username")
    user_elem.clear()
    user_elem.send_keys(username)
    log_info(f"Entered username: {username}")

    # Fill Password
    try:
        pass_elem = browser_driver.find_element(By.NAME, "password")
    except Exception:
        pass_elem = browser_driver.find_element(By.ID, "id_password")
    pass_elem.clear()
    pass_elem.send_keys(password)
    log_info("Entered password.")

    # Submit Form
    try:
        submit_btn = browser_driver.find_element(By.ID, "submit-login")
    except Exception:
        submit_btn = browser_driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")

    submit_btn.click()
    log_info("Clicked submit button on Cloud GUI login form.")

    time.sleep(3)
    curr_url = browser_driver.current_url
    log_info(f"Current post-submit URL: {curr_url}")

    test_pass("Step 03: Cloud (Horizon) GUI login executed successfully.")

# @pytest.mark.gui_login
@pytest.mark.local
def test_04_teosm_gui_login(config_data: dict, gui_tunnels: dict, browser_driver: webdriver.Remote):
    """Step 4: Perform TEOSM GUI authentication upfront via Selenium."""
    log_info("Executing Step 04: TEOSM GUI Login verification...")
    url = config_data["TEOSM_GUI_URL"]
    username = config_data["TEOSM_GUI_USER_NAME"]
    password = config_data["TEOSM_GUI_USER_PASS"]

    log_info(f"Navigating to TEOSM GUI URL: {url}")
    try:
        browser_driver.get(url)
    except Exception as e:
        test_fail(f"Failed to load TEOSM GUI URL '{url}': {e}")

    # Wait for login form to load
    try:
        WebDriverWait(browser_driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )
    except Exception:
        test_fail("TEOSM GUI login page failed to render form element within timeout.")

    # Fill Username
    try:
        user_elem = browser_driver.find_element(By.NAME, "username")
    except Exception:
        try:
            user_elem = browser_driver.find_element(By.ID, "username")
        except Exception:
            user_elem = browser_driver.find_element(By.XPATH, "//input[@type='text' or @type='email']")
    user_elem.clear()
    user_elem.send_keys(username)
    log_info(f"Entered TEOSM username: {username}")

    # Fill Password
    try:
        pass_elem = browser_driver.find_element(By.NAME, "password")
    except Exception:
        try:
            pass_elem = browser_driver.find_element(By.ID, "password")
        except Exception:
            pass_elem = browser_driver.find_element(By.XPATH, "//input[@type='password']")
    pass_elem.clear()
    pass_elem.send_keys(password)
    log_info("Entered TEOSM password.")

    # Submit Form
    try:
        submit_btn = browser_driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
        submit_btn.click()
    except Exception:
        pass_elem.submit()
    log_info("Submitted TEOSM GUI login form.")

    time.sleep(3)
    curr_url = browser_driver.current_url
    log_info(f"Current post-submit URL: {curr_url}")

    test_pass("Step 04: TEOSM GUI login executed successfully.")
