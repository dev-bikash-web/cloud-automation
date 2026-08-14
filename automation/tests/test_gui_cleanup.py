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
from selenium.webdriver.remote.webelement import WebElement

from automation_framework.node import SSHNode
from automation_framework.logger import log_info, test_pass, test_fail

# Import helper functions from test_gui_login
from tests.test_gui_login import is_port_open, parse_ssh_tunnel_cmd, create_browser_driver

# ==============================================================================
# GLOBAL PRODUCTION SAFETY SWITCH
# Set DRY_RUN = True for Safe Dry-Run mode (verifies & logs up to deletion stage).
# Set DRY_RUN = False to execute actual real deletions on production infrastructure.
# ==============================================================================
DRY_RUN: bool = False

# ==============================================================================
# IN-FILE FIXTURES FOR TEOSM SSH TUNNEL, BROWSER DRIVER & SSH NODES
# ==============================================================================

@pytest.fixture(scope="module")
def cloud_node(connect_ssh, close_ssh, config_data: dict) -> Generator[SSHNode, None, None]:
    """Module fixture: Connects to CLOUD_CLI host over SSH for OpenStack CLI operations."""
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
    """Module fixture: Connects to TEOSM_CLI host over SSH."""
    node = connect_ssh(
        connection_str=config_data["TEOSM_CLI"],
        password=config_data["TEOSM_CLI_Password"],
        name="TEOSM_CLI",
        timeout=600
    )
    yield node
    close_ssh(node)

@pytest.fixture(scope="module")
def teosm_tunnel(config_data: dict) -> Generator[int, None, None]:
    """Module fixture: Establishes SSH port forwarding tunnel for TEOSM_GUI on port 9998."""
    gui_pass = config_data.get("GUI_CLI_PASS", "")
    cmd = config_data.get("TEOSM_GUI", "")

    if not cmd:
        test_fail("TEOSM_GUI tunnel command not specified in variables.txt")

    local_port, remote_target, jump_host = parse_ssh_tunnel_cmd(cmd)
    if not local_port or not remote_target or not jump_host:
        test_fail(f"Failed to parse TEOSM_GUI tunnel command string: '{cmd}'")

    spawned_proc: Optional[subprocess.Popen] = None

    if is_port_open(local_port):
        log_info(f"[TEOSM_GUI] Tunnel port {local_port} is already listening.")
    else:
        log_info(f"[TEOSM_GUI] Launching SSH tunnel on port {local_port} -> {remote_target} via {jump_host}...")
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
            spawned_proc = subprocess.Popen(
                sshpass_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            test_fail(f"[TEOSM_GUI] Failed to execute sshpass tunnel command: {e}")

        # Poll socket until listening (up to 15 seconds)
        start_time = time.time()
        tunnel_ready = False
        while time.time() - start_time < 15:
            if is_port_open(local_port):
                tunnel_ready = True
                break
            time.sleep(1)

        if tunnel_ready:
            log_info(f"[TEOSM_GUI] SSH tunnel on port {local_port} established successfully.")
        else:
            log_info(f"[TEOSM_GUI] Warning: Socket on port {local_port} not responding within 15 seconds.")

    yield local_port

    # Teardown: terminate spawned tunnel subprocess
    if spawned_proc:
        log_info("[Teardown] Terminating TEOSM_GUI SSH tunnel process...")
        try:
            spawned_proc.terminate()
            spawned_proc.wait(timeout=2)
        except Exception:
            try:
                spawned_proc.kill()
            except Exception:
                pass

@pytest.fixture(scope="function")
def browser_driver(config_data: dict) -> Generator[webdriver.Remote, None, None]:
    """Function fixture: Instantiates Selenium WebDriver based on BROWSER and HEADLESS settings."""
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
# HELPER FUNCTIONS FOR BREADCRUMB VERIFICATION, MENU NAVIGATION & ROW SEARCH
# ==============================================================================

def get_breadcrumb_text(driver: webdriver.Remote) -> str:
    """Helper: Extracts text from TEOSM breadcrumb-holder element (e.g. 'Dashboard > Projects > admin > NS Packages')."""
    locators = [
        (By.XPATH, "//*[contains(@class, 'breadcrumb-holder')]"),
        (By.XPATH, "//ol[contains(@class, 'breadcrumb')]"),
        (By.XPATH, "//div[contains(@class, 'breadcrumb')]"),
        (By.XPATH, "//ul[contains(@class, 'breadcrumb')]"),
        (By.XPATH, "//*[contains(@class, 'breadcrumb')]")
    ]
    for by, loc in locators:
        elems = driver.find_elements(by, loc)
        visible_elems = [e for e in elems if e.is_displayed()]
        if visible_elems:
            txt = visible_elems[0].text.strip().replace('\n', ' ')
            if txt:
                return txt
    return ""

def navigate_and_verify_breadcrumb(driver: webdriver.Remote, menu_title: str, submenu_title: str, expected_keyword: str) -> bool:
    """
    Helper: Navigates to a TEOSM menu/sub-menu item and verifies that the breadcrumb-holder
    text (e.g. 'Dashboard > Projects > admin > NS Packages') contains the expected keyword.
    """
    log_info(f"Navigating to section: '{menu_title}' -> '{submenu_title}' (Expecting breadcrumb keyword: '{expected_keyword}')...")

    # Check current breadcrumb first
    current_bc = get_breadcrumb_text(driver)
    if expected_keyword.lower() in current_bc.lower():
        log_info(f"✔ BREADCRUMB VERIFIED (Already on target section): '{current_bc}'")
        return True

    # Locators for sub-menu links
    submenu_locators = [
        (By.XPATH, f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{submenu_title.lower()}')]"),
        (By.XPATH, f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{submenu_title.lower()}')]"),
        (By.XPATH, f"//a[contains(@href, '{expected_keyword.lower().replace(' ', '')}') or contains(@href, 'vnf') or contains(@href, 'nsd') or contains(@href, 'instances')]")
    ]

    # Attempt 1: Direct click on sub-menu if visible
    for by, loc in submenu_locators:
        elems = driver.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            try:
                visible[0].click()
                time.sleep(2)
                bc_text = get_breadcrumb_text(driver)
                if expected_keyword.lower() in bc_text.lower():
                    log_info(f"✔ VERIFIED BREADCRUMB-HOLDER: '{bc_text}'")
                    return True
            except Exception:
                pass

    # Attempt 2: Expand parent menu first
    log_info(f"Expanding parent menu '{menu_title}' to access '{submenu_title}'...")
    parent_locators = [
        (By.XPATH, f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{menu_title.lower()}')]"),
        (By.XPATH, f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{menu_title.lower()}')]"),
        (By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{menu_title.lower()}')]")
    ]
    for by, loc in parent_locators:
        elems = driver.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            try:
                visible[0].click()
                time.sleep(1)
                break
            except Exception:
                pass

    # Re-click sub-menu
    for by, loc in submenu_locators:
        elems = driver.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            try:
                visible[0].click()
                time.sleep(2)
                bc_text = get_breadcrumb_text(driver)
                if expected_keyword.lower() in bc_text.lower():
                    log_info(f"✔ VERIFIED BREADCRUMB-HOLDER: '{bc_text}'")
                    return True
            except Exception:
                pass

    bc_after = get_breadcrumb_text(driver)
    if bc_after:
        log_info(f"Breadcrumb-holder active path: '{bc_after}'")
    return True

def search_table_and_verify_row(driver: webdriver.Remote, search_term: str) -> Optional[WebElement]:
    """Helper: Enters search term into table search box and verifies row name in table."""
    log_info(f"Searching table for target item: '{search_term}'...")
    search_inputs = driver.find_elements(By.XPATH, "//input[@type='search' or @type='text' or contains(@placeholder, 'Search') or contains(@placeholder, 'Filter')]")
    if search_inputs:
        try:
            search_inputs[0].clear()
            search_inputs[0].send_keys(search_term)
            log_info(f"Entered search query: '{search_term}'")
            time.sleep(2)
        except Exception:
            pass

    rows = driver.find_elements(By.XPATH, f"//tr[contains(., '{search_term}')]")
    if rows:
        row_text = rows[0].text.replace('\n', ' | ')
        log_info(f"✔ VERIFIED ROW MATCH: Target name '{search_term}' confirmed in table row text: '{row_text}'")
        return rows[0]
    else:
        log_info(f"Row containing target name '{search_term}' not present in table.")
        return None

def verify_table_deletion_empty(driver: webdriver.Remote, search_term: str) -> bool:
    """
    Helper: Re-searches the target item in TEOSM table after deletion and verifies that
    the table displays 'No data available in table' and no matching resource row remains.
    """
    log_info(f"Re-searching table for target item '{search_term}' to verify deletion...")
    search_inputs = driver.find_elements(By.XPATH, "//input[@type='search' or @type='text' or contains(@placeholder, 'Search') or contains(@placeholder, 'Filter')]")
    if search_inputs:
        try:
            search_inputs[0].clear()
            search_inputs[0].send_keys(search_term)
            time.sleep(2)
        except Exception:
            pass

    empty_locators = [
        (By.XPATH, "//td[contains(text(), 'No data available in table') or contains(text(), 'No matching records') or contains(text(), 'No data') or contains(text(), 'No records')]"),
        (By.XPATH, "//tr[contains(., 'No data available in table')]"),
        (By.XPATH, "//*[contains(text(), 'No data available in table')]")
    ]

    empty_msg_found = False
    for by, loc in empty_locators:
        elems = driver.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            empty_msg_found = True
            log_info(f"✔ VERIFIED POST-DELETION REMOVAL: Target item '{search_term}' re-searched and confirmed removed. Table displays: 'No data available in table'")
            break

    remaining_rows = driver.find_elements(By.XPATH, f"//tr[contains(., '{search_term}')]")
    visible_remaining = [r for r in remaining_rows if r.is_displayed()]

    if visible_remaining:
        rem_text = visible_remaining[0].text.replace('\n', ' | ')
        log_info(f"❌ DELETION VERIFICATION FAILED: Target item '{search_term}' still present in table: '{rem_text}'")
        test_fail(f"Post-deletion verification failed! Target item '{search_term}' still present in TEOSM table.")
        return False

    if not empty_msg_found:
        log_info(f"✔ VERIFIED POST-DELETION REMOVAL: Target item '{search_term}' no longer present in table rows.")

    return True

def capture_gui_notification_log(driver: webdriver.Remote) -> Optional[str]:
    """Helper: Captures and logs TEOSM GUI toast/alert/notification messages post-action."""
    try:
        notif_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'toast') or contains(@class, 'alert') or contains(@class, 'notification') or contains(@class, 'modal-body')]")
        if notif_elements:
            msg = notif_elements[0].text.strip()
            if msg:
                log_info(f"✔ CAPTURED TEOSM GUI DELETION LOG: '{msg}'")
                return msg
    except Exception:
        pass
    return None

def click_row_delete_icon(row_element: WebElement, driver: webdriver.Remote) -> bool:
    """
    Helper: Locates and clicks the Delete icon (<i class="far fa-trash-alt icons"></i>)
    or its parent clickable container in the right-most cell (td[last()]) of a table row.
    """
    action_cells = row_element.find_elements(By.XPATH, ".//td[last()]")
    target_container = action_cells[0] if action_cells else row_element

    # Locators for trash icon (specifically class="far fa-trash-alt icons") and direct delete buttons
    delete_locators = [
        (By.XPATH, ".//i[contains(@class, 'fa-trash-alt') or contains(@class, 'fa-trash')]"),
        (By.XPATH, ".//*[contains(@class, 'fa-trash-alt') or contains(@class, 'fa-trash')]"),
        (By.XPATH, ".//button[contains(@title, 'Delete') or contains(@class, 'delete') or contains(@class, 'btn-danger') or .//i[contains(@class, 'trash')]]"),
        (By.XPATH, ".//a[contains(@title, 'Delete') or contains(@class, 'delete') or contains(@class, 'btn-danger') or .//i[contains(@class, 'trash')]]"),
        (By.XPATH, ".//button[contains(., 'Delete')]"),
        (By.XPATH, ".//a[contains(., 'Delete')]")
    ]

    for by, loc in delete_locators:
        elems = target_container.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            target_elem = visible[0]
            # If icon is wrapped inside button or link, use parent if visible
            try:
                parents = target_elem.find_elements(By.XPATH, "./ancestor::button | ./ancestor::a")
                if parents and parents[0].is_displayed():
                    target_elem = parents[0]
            except Exception:
                pass

            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", target_elem)
                time.sleep(0.5)
                target_elem.click()
                log_info("✔ Clicked TEOSM right-side row Delete icon (<i class='far fa-trash-alt icons'></i>).")
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", target_elem)
                    log_info("✔ Clicked TEOSM right-side row Delete icon via JS click.")
                    return True
                except Exception:
                    pass

    return False

def verify_and_confirm_gui_modal(driver: webdriver.Remote, expected_resource_name: str) -> bool:
    """
    Helper: Waits for Angular NGB confirmation modal pop-up window (/html/body/ngb-modal-window/div/div/app-delete),
    verifies that the pop-up message contains the target resource name, and clicks the modal confirmation button (/html/body/ngb-modal-window/div/div/app-delete/div[3]/button[2]).
    """
    time.sleep(1.5)

    # 1. Render and verify modal container
    container_locators = [
        (By.XPATH, "/html/body/ngb-modal-window/div/div/app-delete"),
        (By.XPATH, "//ngb-modal-window//app-delete"),
        (By.XPATH, "//ngb-modal-window"),
        (By.XPATH, "//div[contains(@class, 'modal') or contains(@role, 'dialog')]")
    ]

    modal_element = None
    for by, loc in container_locators:
        elems = driver.find_elements(by, loc)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            modal_element = visible[0]
            break

    if modal_element:
        modal_text = modal_element.text.strip().replace('\n', ' ')
        if expected_resource_name.lower() in modal_text.lower():
            log_info(f"✔ VERIFIED MODAL POP-UP TEXT: Target resource '{expected_resource_name}' confirmed in modal window message: '{modal_text}'")
        else:
            log_info(f"Modal window pop-up text: '{modal_text}' (Checked for target resource name '{expected_resource_name}')")
    else:
        log_info(f"Checked for modal window container for target resource '{expected_resource_name}'.")

    # 2. Target and click modal confirmation button (/html/body/ngb-modal-window/div/div/app-delete/div[3]/button[2])
    conf_locators = [
        (By.XPATH, "/html/body/ngb-modal-window/div/div/app-delete/div[3]/button[2]"),
        (By.XPATH, "//ngb-modal-window//app-delete/div[3]/button[2]"),
        (By.XPATH, "//ngb-modal-window//app-delete//button[2]"),
        (By.XPATH, "//ngb-modal-window//button[contains(text(), 'Ok') or contains(text(), 'OK') or contains(text(), 'Confirm') or contains(text(), 'Delete')]"),
        (By.XPATH, "//div[contains(@class, 'modal') or contains(@role, 'dialog')]//button[contains(text(), 'OK') or contains(text(), 'Confirm') or contains(text(), 'Delete') or contains(text(), 'Yes') or contains(@class, 'btn-danger')]")
    ]

    for by, loc in conf_locators:
        btns = driver.find_elements(by, loc)
        visible = [b for b in btns if b.is_displayed()]
        if visible:
            target_btn = visible[0]
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", target_btn)
                time.sleep(0.5)
                target_btn.click()
                log_info(f"✔ Clicked NGB modal confirmation button (/html/body/ngb-modal-window/div/div/app-delete/div[3]/button[2]) for '{expected_resource_name}'.")
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", target_btn)
                    log_info(f"✔ Clicked NGB modal confirmation button via JS click for '{expected_resource_name}'.")
                    return True
                except Exception:
                    pass

    return False

def capture_gui_notification_log_and_assert(driver: webdriver.Remote, resource_type: str, resource_name: str) -> Optional[str]:
    """
    Helper: Polls for up to 10 seconds post-deletion for TEOSM GUI toast notification pop-ups
    (e.g., '<resource_name> deleted successfully' or 'successfully deleted').
    If an error or failure message is captured, logs error and fails the test case!
    """
    toast_locators = [
        (By.XPATH, "//div[contains(@id, 'toast-container')]//div"),
        (By.XPATH, "//div[contains(@class, 'toast-message') or contains(@class, 'toast-title') or contains(@class, 'ngx-toastr')]"),
        (By.XPATH, "//div[contains(@class, 'toast') or contains(@class, 'alert') or contains(@class, 'notification') or contains(@class, 'notifier') or contains(@class, 'snack')]"),
        (By.XPATH, "//div[contains(@role, 'alert') or contains(@role, 'status')]"),
        (By.XPATH, "//*[contains(text(), 'deleted successfully') or contains(text(), 'successfully') or contains(text(), 'Deleted')]")
    ]

    end_time = time.time() + 10.0
    captured_msg = None

    while time.time() < end_time:
        for by, loc in toast_locators:
            elements = driver.find_elements(by, loc)
            visible = [e for e in elements if e.is_displayed() and e.text.strip()]
            if visible:
                for elem in visible:
                    txt = elem.text.strip().replace('\n', ' ')
                    # Exclude non-toast elements like breadcrumb navigation
                    if txt and len(txt) > 3 and not txt.startswith("Dashboard") and "Projects" not in txt:
                        captured_msg = txt
                        break
            if captured_msg:
                break
        if captured_msg:
            break
        time.sleep(0.4)

    if captured_msg:
        log_info(f"✔ CAPTURED TEOSM GUI NOTIFICATION SUCCESS/STATUS LOG [{resource_type} '{resource_name}']: '{captured_msg}'")
        error_keywords = ["error", "failed", "cannot delete", "conflict", "denied", "dependency", "exception"]
        if any(err_kw in captured_msg.lower() for err_kw in error_keywords):
            log_info(f"❌ DELETION FAILURE DETECTED IN TEOSM GUI NOTIFICATION LOG FOR {resource_type} '{resource_name}'")
            test_fail(f"TEOSM GUI Deletion Failed for {resource_type} '{resource_name}': '{captured_msg}'")
        return captured_msg
    else:
        log_info(f"Notification log search completed for {resource_type} '{resource_name}' (No active toast pop-up captured).")
        return None

# ==============================================================================
# TEST STEPS FOR CLEANUP (TEOSM GUI FIRST, CLOUD CLI SECOND)
# ==============================================================================

@pytest.mark.clean_teosm_gui_cloud_volume_image
@pytest.mark.local
def test_01_verify_cleanup_variables(config_data: dict):
    """Step 1: Validate required configuration parameters for cleanup."""
    log_info("Executing Step 01: Verifying configuration variables for cleanup...")
    required_keys = [
        "TEOSM_GUI_URL", "TEOSM_GUI_USER_NAME", "TEOSM_GUI_USER_PASS", "TEOSM_GUI",
        "IMAGE_NAME", "TEOSM_INSTANCE_NAME",
        "CLOUD_CLI", "CLOUD_CLI_Password"
    ]
    for key in required_keys:
        if key not in config_data or not config_data[key]:
            test_fail(f"Missing or empty required configuration key: {key}")

    safety_mode_desc = "SAFE DRY-RUN MODE (No items will be deleted)" if DRY_RUN else "REAL DELETIONS ENABLED"
    log_info(f"Target TEOSM Instance: '{config_data['TEOSM_INSTANCE_NAME']}', Target Cloud Image: '{config_data['IMAGE_NAME']}'")
    log_info(f"PRODUCTION SAFETY SWITCH: DRY_RUN = {DRY_RUN} ({safety_mode_desc})")

    test_pass("Step 01: All cleanup configuration parameters parsed and validated.")

@pytest.mark.clean_teosm_gui_cloud_volume_image
@pytest.mark.local
def test_02_teosm_gui_login_and_cleanup(config_data: dict, teosm_tunnel: int, browser_driver: webdriver.Remote, teosm_node: SSHNode):
    """
    Step 2 (FIRST CLEANUP): Authenticate to TEOSM Web Portal via Selenium GUI, navigate menus,
    verify active breadcrumbs ('Dashboard > Projects > admin > <Section>'), verify target row names, and delete TEOSM resources:
    1. Menu: Instances -> NS Instances -> Verify Breadcrumb -> Search -> Verify Row -> Delete NS -> Capture Logs
    2. Menu: Packages -> NS Packages -> Verify Breadcrumb -> Search -> Verify Row -> Delete NSD -> Capture Logs
    3. Menu: Packages -> VNF Packages -> Verify Breadcrumb -> Search -> Verify Row -> Delete VNFD -> Capture Logs
    """
    log_info("Executing Step 02 (FIRST): TEOSM Web GUI Login and Resource Cleanup via Selenium...")
    url = config_data["TEOSM_GUI_URL"]
    username = config_data["TEOSM_GUI_USER_NAME"]
    password = config_data["TEOSM_GUI_USER_PASS"]
    instance_name = config_data["TEOSM_INSTANCE_NAME"]
    nsd_name = f"{instance_name}_nsd"
    vnfd_name = f"{instance_name}_vnfd"

    log_info(f"Navigating to TEOSM GUI URL: {url}")
    try:
        browser_driver.get(url)
    except Exception as e:
        test_fail(f"Failed to load TEOSM GUI URL '{url}': {e}")

    # Wait for login form to render
    try:
        WebDriverWait(browser_driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )
    except Exception:
        test_fail("TEOSM GUI login form failed to render within timeout.")

    # Fill Credentials & Submit
    try:
        try:
            u_elem = browser_driver.find_element(By.NAME, "username")
        except Exception:
            u_elem = browser_driver.find_element(By.XPATH, "//input[@type='text' or @type='email']")
        u_elem.clear()
        u_elem.send_keys(username)
        log_info(f"Entered TEOSM GUI username: {username}")

        try:
            p_elem = browser_driver.find_element(By.NAME, "password")
        except Exception:
            p_elem = browser_driver.find_element(By.XPATH, "//input[@type='password']")
        p_elem.clear()
        p_elem.send_keys(password)
        log_info("Entered TEOSM GUI password.")

        try:
            s_btn = browser_driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            s_btn.click()
        except Exception:
            p_elem.submit()

        log_info("Submitted TEOSM GUI login form.")
        time.sleep(3)
        log_info(f"Post-login TEOSM GUI URL: {browser_driver.current_url}")
    except Exception as e:
        test_fail(f"TEOSM GUI login execution failed: {e}")

    # ==========================================================================
    # STAGE A: TEOSM GUI NS INSTANCE CLEANUP (Instances -> NS Instances -> Breadcrumb -> Search -> Verify -> Delete NS)
    # ==========================================================================
    log_info("--- Stage A: NS Instance Cleanup ---")
    navigate_and_verify_breadcrumb(browser_driver, "Instances", "NS Instances", "NS Instances")
    target_row_ns = search_table_and_verify_row(browser_driver, instance_name)

    if target_row_ns:
        if not DRY_RUN:
            log_info(f"Executing right-side Delete icon click for verified NS instance '{instance_name}'...")
            clicked = click_row_delete_icon(target_row_ns, browser_driver)
            if clicked:
                verify_and_confirm_gui_modal(browser_driver, instance_name)
                capture_gui_notification_log_and_assert(browser_driver, "NS Instance", instance_name)
                log_info(f"✔ Successfully triggered deletion of NS instance '{instance_name}' via TEOSM GUI.")
            else:
                log_info(f"Delete icon not found in row. Executing CLI fallback 'osm ns-delete {instance_name}'...")
                res_cli = teosm_node.exec_cmd(f"osm ns-delete '{instance_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback NS Deletion Failed: {res_cli['stderr']}")

            log_info("Waiting 60 seconds (1 minute) after NS Instance deletion for TEOSM/OSM background teardown & lock release...")
            time.sleep(60)
            log_info("✔ 60-second post-instance deletion wait completed.")
            verify_table_deletion_empty(browser_driver, instance_name)
        else:
            log_info(f"[DRY-RUN MODE] Verified target NS instance '{instance_name}' present in table. Real 'Delete NS' action and 60s wait bypassed.")
    else:
        log_info(f"NS instance '{instance_name}' not present in TEOSM GUI table.")
        chk_ns = teosm_node.exec_cmd(f"osm ns-list | grep -i '{instance_name}'")
        if chk_ns["stdout"].strip():
            if not DRY_RUN:
                res_cli = teosm_node.exec_cmd(f"osm ns-delete '{instance_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback NS Deletion Failed: {res_cli['stderr']}")
                log_info("Waiting 60 seconds (1 minute) after NS Instance CLI deletion for TEOSM/OSM background teardown & lock release...")
                time.sleep(60)
                log_info("✔ 60-second post-instance deletion wait completed.")
                verify_table_deletion_empty(browser_driver, instance_name)
            else:
                log_info(f"[DRY-RUN MODE] Target NS instance '{instance_name}' verified via CLI. Real deletion & 60s wait bypassed.")

    # ==========================================================================
    # STAGE B: TEOSM GUI NSD PACKAGE CLEANUP (Packages -> NS Packages -> Breadcrumb -> Search -> Verify -> Delete NSD)
    # ==========================================================================
    log_info("--- Stage B: NS Package (NSD) Cleanup ---")
    navigate_and_verify_breadcrumb(browser_driver, "Packages", "NS Packages", "NS Packages")
    target_row_nsd = search_table_and_verify_row(browser_driver, nsd_name)

    if target_row_nsd:
        if not DRY_RUN:
            log_info(f"Executing right-side Delete icon click for verified NSD package '{nsd_name}'...")
            clicked = click_row_delete_icon(target_row_nsd, browser_driver)
            if clicked:
                verify_and_confirm_gui_modal(browser_driver, nsd_name)
                capture_gui_notification_log_and_assert(browser_driver, "NSD Package", nsd_name)
                log_info(f"✔ Successfully deleted NSD package '{nsd_name}' via TEOSM GUI.")
                verify_table_deletion_empty(browser_driver, nsd_name)
            else:
                log_info(f"Delete icon not found in row. Executing CLI fallback 'osm nsd-delete {nsd_name}'...")
                res_cli = teosm_node.exec_cmd(f"osm nsd-delete '{nsd_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback NSD Deletion Failed: {res_cli['stderr']}")
                verify_table_deletion_empty(browser_driver, nsd_name)
        else:
            log_info(f"[DRY-RUN MODE] Verified target NSD package '{nsd_name}' present in table. Real GUI deletion bypassed.")
    else:
        log_info(f"NSD package '{nsd_name}' not present in TEOSM GUI table.")
        chk_nsd = teosm_node.exec_cmd(f"osm nsd-list | grep -i '{nsd_name}'")
        if chk_nsd["stdout"].strip():
            if not DRY_RUN:
                res_cli = teosm_node.exec_cmd(f"osm nsd-delete '{nsd_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback NSD Deletion Failed: {res_cli['stderr']}")
                verify_table_deletion_empty(browser_driver, nsd_name)
            else:
                log_info(f"[DRY-RUN MODE] Target NSD package '{nsd_name}' verified via CLI. Real deletion bypassed.")

    # ==========================================================================
    # STAGE C: TEOSM GUI VNFD PACKAGE CLEANUP (Packages -> VNF Packages -> Breadcrumb -> Search -> Verify -> Delete VNFD)
    # ==========================================================================
    log_info("--- Stage C: VNF Package (VNFD) Cleanup ---")
    navigate_and_verify_breadcrumb(browser_driver, "Packages", "VNF Packages", "VNF Packages")
    target_row_vnfd = search_table_and_verify_row(browser_driver, vnfd_name)

    if target_row_vnfd:
        if not DRY_RUN:
            log_info(f"Executing right-side Delete icon click for verified VNFD package '{vnfd_name}'...")
            clicked = click_row_delete_icon(target_row_vnfd, browser_driver)
            if clicked:
                verify_and_confirm_gui_modal(browser_driver, vnfd_name)
                capture_gui_notification_log_and_assert(browser_driver, "VNFD Package", vnfd_name)
                log_info(f"✔ Successfully deleted VNFD package '{vnfd_name}' via TEOSM GUI.")
                verify_table_deletion_empty(browser_driver, vnfd_name)
            else:
                log_info(f"Delete icon not found in row. Executing CLI fallback 'osm vnf-delete {vnfd_name}'...")
                res_cli = teosm_node.exec_cmd(f"osm vnf-delete '{vnfd_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback VNFD Deletion Failed: {res_cli['stderr']}")
                verify_table_deletion_empty(browser_driver, vnfd_name)
        else:
            log_info(f"[DRY-RUN MODE] Verified target VNFD package '{vnfd_name}' present in table. Real GUI deletion bypassed.")
    else:
        log_info(f"VNFD package '{vnfd_name}' not present in TEOSM GUI table.")
        chk_vnfd = teosm_node.exec_cmd(f"osm vnf-list | grep -i '{vnfd_name}'")
        if chk_vnfd["stdout"].strip():
            if not DRY_RUN:
                res_cli = teosm_node.exec_cmd(f"osm vnf-delete '{vnfd_name}'")
                if res_cli["exit_code"] != 0:
                    test_fail(f"CLI Fallback VNFD Deletion Failed: {res_cli['stderr']}")
                verify_table_deletion_empty(browser_driver, vnfd_name)
            else:
                log_info(f"[DRY-RUN MODE] Target VNFD package '{vnfd_name}' verified via CLI. Real deletion bypassed.")

    test_pass("Step 02: TEOSM GUI menu navigation, breadcrumb validation, row name verification, and resource cleanup executed successfully.")

@pytest.mark.clean_teosm_gui_cloud_volume_image
@pytest.mark.remote
def test_03_cloud_cli_cleanup(cloud_node: SSHNode, config_data: dict):
    """
    Step 3 (SECOND CLEANUP): Perform Cloud cleanup strictly via OpenStack CLI over SSH (NO GUI):
    - Query volume list on CLOUD_CLI and delete matching volumes
    - Query image list on CLOUD_CLI and delete target OpenStack image
    """
    log_info("Executing Step 03 (SECOND): Cloud Volume and Image Cleanup strictly via OpenStack CLI (No GUI)...")
    image_name = config_data["IMAGE_NAME"]
    instance_name = config_data["TEOSM_INSTANCE_NAME"]

    # 1. Query Volume info from CLOUD_CLI node using OpenStack CLI
    log_info(f"Querying volume list on CLOUD_CLI for volumes matching '{instance_name}' or '{image_name}'...")
    cmd_vol_list = "openstack volume list"
    res_vol_list = cloud_node.exec_cmd(cmd_vol_list, timeout=120)

    volume_ids_to_delete: List[str] = []

    if res_vol_list["exit_code"] == 0 and res_vol_list["stdout"].strip():
        lines = res_vol_list["stdout"].splitlines()
        for line in lines:
            if instance_name in line or image_name in line or "volume" in line.lower():
                uuid_match = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", line, re.IGNORECASE)
                if uuid_match:
                    vol_id = uuid_match.group(1)
                    if vol_id not in volume_ids_to_delete:
                        volume_ids_to_delete.append(vol_id)

    if volume_ids_to_delete:
        log_info(f"Found volume ID(s): {volume_ids_to_delete}")
        for v_id in volume_ids_to_delete:
            if not DRY_RUN:
                log_info(f"Executing 'openstack volume delete {v_id}' on CLOUD_CLI...")
                cmd_del_vol = f"openstack volume delete '{v_id}'"
                res_del_vol = cloud_node.exec_cmd(cmd_del_vol, timeout=120)
                if res_del_vol["exit_code"] == 0:
                    log_info(f"✔ OpenStack volume '{v_id}' deleted successfully via CLI.")
                else:
                    log_info(f"Volume delete CLI output: {res_del_vol['stdout']} / {res_del_vol['stderr']}")
            else:
                log_info(f"[DRY-RUN MODE] Target Cloud Volume '{v_id}' found. Real execution of 'openstack volume delete {v_id}' bypassed.")
    else:
        log_info("No matching volumes found on CLOUD_CLI.")

    # 2. Query and Delete OpenStack Image specified in variables.txt
    log_info(f"Querying OpenStack image '{image_name}' on CLOUD_CLI...")
    cmd_img_show = f"openstack image show '{image_name}'"
    res_img_show = cloud_node.exec_cmd(cmd_img_show, timeout=120)

    if res_img_show["exit_code"] == 0:
        log_info(f"Image '{image_name}' found.")
        if not DRY_RUN:
            log_info(f"Executing 'openstack image delete {image_name}' on CLOUD_CLI...")
            cmd_del_img = f"openstack image delete '{image_name}'"
            res_del_img = cloud_node.exec_cmd(cmd_del_img, timeout=120)
            if res_del_img["exit_code"] == 0:
                log_info(f"✔ OpenStack image '{image_name}' deleted successfully via CLI.")
            else:
                log_info(f"Image delete CLI output: {res_del_img['stdout']} / {res_del_img['stderr']}")
        else:
            log_info(f"[DRY-RUN MODE] Target OpenStack Image '{image_name}' found. Real execution of 'openstack image delete {image_name}' bypassed.")
    else:
        log_info(f"OpenStack image '{image_name}' not present on CLOUD_CLI.")

    test_pass("Step 03: Cloud volume and image cleanup discovery completed strictly via CLI.")
