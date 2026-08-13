# Automation Framework API Specification & Code Examples

This document provides a comprehensive API specification, code syntax examples, parameter descriptions, and return value schemas for all modules in [`automation_framework/`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework) and the generic wrapper fixtures in [`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py).

---

## 1. Generic Wrapper Fixture APIs ([`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py))

[`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py) acts as a **generic, host-decoupled wrapper library**. It does not hardcode target host details, allowing any test case or test module to connect to any remote node on demand.

### 1.1 `config_data` Fixture

* **Scope**: `session` (Executes **ONCE** per test session)
* **Syntax**: `def config_data() -> Dict[str, str]`
* **Description**: Parses [`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt) once at session startup and provides a cached configuration dictionary to any test function.

---

### 1.2 `connect_ssh` Factory Wrapper Fixture

* **Scope**: `session`
* **Syntax**: 
  ```python
  def connect_ssh() -> Callable[[str, str, str, int], SSHNode]
  ```
* **Description**: A generic SSH connection factory wrapper. Accepts target host parameters (`connection_str`, `password`, `name`, `timeout`) and returns a connected [`SSHNode`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/node.py#L8) instance for ANY remote node.

---

### 1.3 `close_ssh` Teardown Wrapper Fixture

* **Scope**: `session`
* **Syntax**: 
  ```python
  def close_ssh() -> Callable[[SSHNode], None]
  ```
* **Description**: A generic SSH connection closure wrapper. Accepts an [`SSHNode`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/node.py#L8) instance and closes its SSH and SFTP connections cleanly.
* **Code Example**:
  ```python
  # Using connect_ssh and close_ssh inside tests/test_node_launch.py
  @pytest.fixture(scope="module")
  def cloud_node(connect_ssh, close_ssh, config_data: dict):
      node = connect_ssh(
          connection_str=config_data["CLOUD_CLI"],
          password=config_data["CLOUD_CLI_Password"],
          name="CLOUD_CLI",
          timeout=600
      )
      yield node
      
      # In-file teardown closes connection using close_ssh wrapper
      close_ssh(node)
  ```

---

## 2. `ConfigParser` Module ([`automation_framework/config.py`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/config.py))

### 2.1 `ConfigParser.parse`

* **Syntax**: `ConfigParser.parse(file_path: str) -> Dict[str, str]`
* **Description**: Parses key=value configuration files (`variables.txt`), ignoring empty lines and comments (`#`).
* **Return Value**: `Dict[str, str]` containing parsed key-value pairs.

### 2.2 `ConfigParser.get_host_credentials`

* **Syntax**: `ConfigParser.get_host_credentials(connection_str: str, default_port: int = 22) -> Tuple[Optional[str], Optional[str], int]`
* **Description**: Parses connection strings formatted as `user@hostname:port` or `user@hostname` into `(username, hostname, port)`.

---

## 3. `SSHNode` Module ([`automation_framework/node.py`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/node.py))

* `SSHNode(hostname, username, password, port=22, name="Node", global_timeout=600)`: Constructor.
* `async connect(...)`: Opens SSH connection & SFTP handle.
* `exec_cmd(command, cwd=None, timeout=None, pty=True) -> Dict[str, Any]`: **Synchronous wrapper** around `run_cmd` that automatically handles the `asyncio` event loop. Returns `{"exit_code": int, "stdout": str, "stderr": str}`.
* `exec_and_match(command, regex_pattern, cwd=None, timeout=None, pty=True, expect_exit_code=0) -> Dict[str, Any]`: **Synchronous wrapper** around `execute_and_match` that automatically handles the `asyncio` event loop and regex matching. Returns `{"match": bool, "stdout": str, "stderr": str}`.
* `async run_cmd(command, cwd=None, timeout=None, pty=True)`: Async remote execution.
* `async execute_and_match(command, regex_pattern, cwd=None, timeout=None, pty=True, expect_exit_code=0)`: Async regex matching.
* `node.sftp.put(local, remote)` / `node.sftp.get(remote, local)`: Direct SFTP file transfers.
* `async close()`: Closes SSH and SFTP connections.

---

## 4. `Logger` & Assertion Helper Module ([`automation_framework/logger.py`](file:///home/bikash/workera/repository/automation_node_launch/automation_framework/logger.py))

* `log_info(msg)`: Prints cyan colored info message.
* `log_success(msg)`: Prints green checkmark success message (`✔ SUCCESS`).
* `log_error(msg)`: Prints red crossmark error message (`✖ ERROR`).
* `log_step(num, title)`: Prints bold step header banner.
* `test_pass(msg)`: Logs green checkmark success message (`✔ SUCCESS: <msg>`). Can be used inside `if` branches.
* `test_fail(msg)`: Logs red crossmark error message (`✖ ERROR: <msg>`) and executes `pytest.fail(msg)` to fail Pytest test case immediately. Can be used inside `else` branches.
