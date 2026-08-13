# Developer Onboarding Guide: Adding New Test Cases & Test Modules

This guide provides step-by-step instructions, coding standards, templates, and Pytest mechanics cheat sheets for creating new test cases or onboarding entirely new test modules in this framework.

---

## 1. Architecture Overview & Generic Wrapper Library

[`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py) acts as a **generic, host-decoupled wrapper library**:
1. **`config_data`** (`session` scope): Reads [`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt) **ONCE per test session** and caches the configuration dictionary.
2. **`connect_ssh`** (`session` scope): A generic **SSH Connection Factory Wrapper**. Accepts host details on demand (`connection_str`, `password`, `name`) and connects to ANY remote node.
3. **In-File Teardown**: Node-specific SSH connections and post-success cleanup hooks live **inside the test file itself** (`tests/test_node_launch.py`).

---

## 2. Naming Conventions & Rules

1. **Test Files**: Must begin with `test_` and use lowercase with underscores (e.g., `tests/test_epdg_health.py`).
2. **Test Functions**: Must begin with `test_` (e.g., `test_01_verify_interface_status`).
3. **Numbering Function Names**: For sequential or ordered pipeline tests, use numeric prefixes (`test_01_...`, `test_02_...`).
4. **Markers**: Every test function must be decorated with at least one marker (`@pytest.mark.local` or `@pytest.mark.remote`).

---

## 3. How to Connect to a New Remote Node (In-File Fixture Pattern)

If your new test module needs to connect to a new remote server (e.g., `HSS_CLI`), use the `connect_ssh` factory wrapper directly inside your new test file:

```python
# tests/test_hss_suite.py
import pytest
import asyncio
from typing import Generator
from automation_framework.node import SSHNode

@pytest.fixture(scope="module")
def hss_node(connect_ssh, config_data: dict) -> Generator[SSHNode, None, None]:
    """In-file module fixture: Connects to HSS_CLI on demand."""
    node = connect_ssh(
        connection_str=config_data["HSS_CLI"],
        password=config_data["HSS_CLI_Password"],
        name="HSS_CLI",
        timeout=600
    )
    yield node
    
    # In-file teardown: closes connection
    loop = get_or_create_event_loop()
    loop.run_until_complete(node.close())

@pytest.mark.remote
def test_check_hss_status(hss_node: SSHNode):
    """Test function using the in-file hss_node connection."""
    loop = get_or_create_event_loop()
    res = loop.run_until_complete(hss_node.run_cmd("systemctl status hss_service"))
    assert res["exit_code"] == 0
```

---

## 4. Copy-Paste Templates for New Tests

### Template A: Local Offline Unit Test (No Remote SSH)

```python
# tests/test_local_utilities.py
import pytest
from automation_framework.config import ConfigParser
from automation_framework.logger import log_info, log_success

@pytest.mark.local
def test_parse_custom_config(tmp_path):
    """Test parsing a temporary configuration file."""
    log_info("Testing custom configuration file parsing...")
    
    cfg = tmp_path / "test_vars.txt"
    cfg.write_text("HOST=172.23.1.100\nPORT=22\n")
    
    data = ConfigParser.parse(str(cfg))
    assert data["HOST"] == "172.23.1.100"
    assert data["PORT"] == "22"
    log_success("Custom configuration parsed successfully.")
```

---

### Template B: Remote SSH Node Test with Regex Matching

```python
# tests/test_remote_diagnostics.py
import pytest
import asyncio
from automation_framework.node import SSHNode
from automation_framework.logger import log_info, log_success

@pytest.mark.remote
def test_check_openstack_service_status(cloud_node: SSHNode, config_data: dict):
    """Test verifying openstack service output via regex."""
    log_info("Executing OpenStack service check on CLOUD_CLI...")
    
    cmd = "openstack service list"
    regex_pattern = r"(nova|neutron|glance|cinder)"
    
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(cloud_node.execute_and_match(
        command=cmd,
        regex_pattern=regex_pattern,
        expect_exit_code=0
    ))
    
    assert res["match"] is True, f"Regex match failed for pattern '{regex_pattern}'"
    log_success("OpenStack core services verified.")
```

---

## 5. How to Run & Validate Your New Tests

- **Run File**: `pytest tests/test_<your_feature>.py`
- **Run Function**: `pytest tests/test_<your_feature>.py -k "test_function_name"`
- **Run Marker**: `pytest -m <your_marker>`
