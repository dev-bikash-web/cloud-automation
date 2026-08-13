# Pytest Framework Architecture & Working Mechanics Guide

This guide explains the internal working procedures of the Pytest engine, fixture lifecycles, memory caching mechanisms, dependency injection, and advanced fixture patterns used in this automation framework.

---

## 1. Pytest Engine Working Procedure & Execution Flow

When you execute `pytest` or `pytest -m local`, the Pytest engine performs a 4-stage execution pipeline:

```
+-----------------------------------------------------------------------------------+
|                         STAGE 1: DISCOVERY & INGESTION                            |
| - Scans project for pytest.ini options and conftest.py files                     |
| - Discovers test files matching test_*.py                                        |
| - Collects test functions matching def test_*                                     |
+----------------------------------------|------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                      STAGE 2: FIXTURE REGISTRATION & LOOKUP                       |
| - Inspects test function parameters using Reflection (Python inspect module)      |
| - Matches parameter string names against registered @pytest.fixture definitions   |
+----------------------------------------|------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                   STAGE 3: DEPENDENCY INJECTION & RAM CACHING                     |
| - Checks internal memory (FixtureDef.cached_result) for active scope cache       |
| - If cached in RAM: Reuses object instantly (e.g. config_data dictionary)        |
| - If not cached: Executes setup block and stores outcome in RAM                  |
+----------------------------------------|------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                   STAGE 4: TEST EXECUTION & TEARDOWN HOOKS                        |
| - Injects cached fixture objects as keyword arguments into test functions        |
| - Evaluates assertions and reports outcome (PASSED / FAILED)                      |
| - Executes yield teardown hooks upon scope expiry                                 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Pytest Fixture Overview & Setup/Teardown Mechanics (`yield`)

A Pytest fixture (`@pytest.fixture`) manages resource preparation (setup), data passing, and resource cleanup (teardown).

### 2.1 What `yield` Does in Pytest Fixtures

The `yield` keyword splits a fixture into **three distinct execution phases**:

1. **Setup Phase (Code BEFORE `yield`)**: Executes **before** the test function runs. Opens SSH sockets, parses files, or creates temporary directories.
2. **Data Handover & Execution Phase (At `yield <value>`)**: Hands over the prepared object/data to Pytest and **pauses** execution. The fixture remains paused at `yield` while tests execute.
3. **Teardown Phase (Code AFTER `yield`)**: Executes **after** tests finish running (based on fixture scope). Pytest resumes execution right after `yield` to close sockets, delete temporary folders, or terminate background processes.

---

### 2.2 Execution Timeline Diagram of `yield`

```
TIMELINE
   │
   ├── 1. SETUP PHASE (Code BEFORE yield):
   │    - Pytest calls fixture setup.
   │    - Opens SSH connection to CLOUD_CLI.
   │
   ├── 2. AT 'yield node':
   │    - Hands connected 'node' object to Pytest.
   │    - Fixture PAUSES at 'yield node'.
   │
   ├── 3. TEST EXECUTION (test_01 ──► test_10):
   │    - Pytest keeps fixture paused at 'yield node'.
   │    - All test functions reuse the SAME connected 'node'.
   │
   ├── 4. SCOPE EXPIRATION:
   │    - Last test finishes; Pytest RESUMES fixture right after 'yield node'.
   │
   └── 5. TEARDOWN PHASE (Code AFTER yield):
        - Pytest executes 'close_ssh(node)'.
        - SSH & SFTP channels close cleanly.
```

---

### 2.3 `return` vs `yield` Comparison

| Feature | `return` | `yield` |
| :--- | :--- | :--- |
| **Setup Code Support** | Yes (supported) | Yes (supported) |
| **Data Handover** | Returns value to test | Yields value to test |
| **Teardown Code Support** | **No** (Function terminates immediately at `return`) | **Yes** (Code after `yield` runs after test completes) |
| **Use Case** | Read-only static data (`config_data`) | Live connections, temporary files, teardown hooks |

---

### 2.4 Concrete Code Examples

#### Example 1: `yield` with Object Handover (SSH Node Connection)
```python
@pytest.fixture(scope="module")
def cloud_node(connect_ssh, close_ssh, config_data: dict):
    # --- 1. SETUP PHASE (Before yield) ---
    log_info("Connecting to CLOUD_CLI...")
    node = connect_ssh(
        connection_str=config_data["CLOUD_CLI"],
        password=config_data["CLOUD_CLI_Password"],
        name="CLOUD_CLI"
    )
    
    # --- 2. DATA HANDOVER & PAUSE (At yield) ---
    yield node  # Hands connected 'node' to test_01 ... test_10
    
    # --- 3. TEARDOWN PHASE (After yield) ---
    log_info("Closing CLOUD_CLI connection...")
    close_ssh(node)  # Executed after test_10 finishes
```

#### Example 2: `yield` without Object Handover (Post-Success Cleanup Hook)
```python
@pytest.fixture(scope="module", autouse=True)
def node_launch_cleanup(request, cloud_node: SSHNode, config_data: dict):
    # --- 1. SETUP PHASE ---
    # Nothing needed before tests start
    
    # --- 2. PAUSE AT YIELD ---
    yield  # Pause while test_01 ... test_10 execute
    
    # --- 3. TEARDOWN PHASE ---
    # Runs automatically after all tests finish
    if hasattr(request.node, "session") and request.session.testsfailed == 0:
        cloud_folder = config_data["CLOUD_NFV_FOLDER"]
        cloud_node.run_cmd(f"rm -rf '{cloud_folder}'")
```

---

## 3. Internal RAM Caching (`cached_result`) & Dependency Injection

### How Pytest Stores Fixture Outcomes
Pytest maintains an internal runtime data structure in RAM called `FixtureDef` (Fixture Definition).

```
Pytest Session Context (RAM Memory)
   └── FixtureManager
         └── FixtureDef (name="config_data", scope="session")
               └── cached_result = ( {"CLOUD_CLI": "cdot@172.23.1.50", ...}, cache_key )
```

1. **`config_data`** (`scope="session"`): Reads [`variables.txt`](file:///home/bikash/workera/repository/automation_node_launch/variables.txt) **ONCE** at startup. The parsed dictionary is saved in `FixtureDef.cached_result`.
2. **Reuse**: Every test function requesting `config_data` receives the exact same cached dictionary from RAM without re-reading disk.

### How Pytest Injects Fixtures into Test Parameters

```python
def test_02_verify_directories(cloud_node: SSHNode, teosm_node: SSHNode, config_data: dict):
```

1. **Reflection**: Pytest inspects the parameter list `["cloud_node", "teosm_node", "config_data"]`.
2. **Type Hints (`: SSHNode`, `: dict`)**: Used for IDE autocompletion and static analysis.
3. **Keyword Binding**: Pytest fetches cached objects from memory and calls `test_02_verify_directories(cloud_node=..., teosm_node=..., config_data=...)`.

---

## 4. Fixture Scopes & Lifespan Matrix

`scope` controls how often setup and teardown code execute:

| Scope | Lifespan | When Setup Runs | When Teardown Runs | Used For |
| :--- | :--- | :--- | :--- | :--- |
| **`function`** *(Default)* | Per Test Function | Before **each test** function | After **each test** function | Isolated temp files |
| **`module`** | Per Test File (`.py`) | Before first test in `.py` file | After last test in `.py` file | Remote SSH node connections |
| **`session`** | Per Entire Test Run | Once at test suite start | Once at test suite end | `config_data`, `connect_ssh` factory |

---

## 5. Automatic Execution (`autouse=True`) vs Explicit Fixture Requests

The `autouse` parameter controls whether a fixture requires explicit parameter invocation or runs automatically.

> [!IMPORTANT]
> **Core Distinction between `yield` and `autouse=True`**:
> - **`yield`** controls **WHEN** code runs (code before `yield` = setup, code after `yield` = teardown).
> - **`autouse=True`** controls **WHO TRIGGERS the fixture** (whether test functions must explicitly request the fixture by name in parameters or whether Pytest forces it to run automatically).

---

### 5.1 The Superpower of `autouse=True`

#### Case 1: Without `autouse=True` (`autouse=False` default)
Pytest will **COMPLETELY IGNORE AND SKIP** your fixture unless at least one test function explicitly lists the fixture name in its arguments:

```python
# conftest.py (autouse=False by default)
@pytest.fixture(scope="module")
def node_launch_cleanup():
    yield
    print("Post-success cleanup executed!")
```

```python
# tests/test_node_launch.py
# If no test function types 'node_launch_cleanup' in its parameters:
def test_01(cloud_node): pass
def test_02(cloud_node, teosm_node): pass

# RESULT: 'node_launch_cleanup' NEVER RUNS! Setup and yield teardown are skipped!
```

---

#### Case 2: With `autouse=True`
You **do not need to modify any test function parameters**. Pytest forces the fixture to run automatically:

```python
# conftest.py
@pytest.fixture(scope="module", autouse=True)
def node_launch_cleanup():
    yield
    print("Post-success cleanup executed!")
```

```python
# tests/test_node_launch.py
# Clean parameter list! No test needs to type 'node_launch_cleanup':
def test_01(cloud_node): pass
def test_02(cloud_node, teosm_node): pass

# RESULT: 'node_launch_cleanup' RUNS AUTOMATICALLY! 
# Teardown after yield executes automatically after test_02 finishes.
```

---

### 5.2 How `autouse=True` Works in Pytest Mechanics

When Pytest collects test cases in a file:
1. **Discovery**: Pytest identifies all fixtures marked with `autouse=True` within the file or [`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py).
2. **Implicit Dependency Injection**: Pytest automatically attaches the `autouse` fixture to **every test function within its scope** as if every test function had explicitly listed the fixture in its arguments.
3. **Scope Interaction**:
   - `scope="function", autouse=True`: Runs setup & teardown automatically before and after **each test function**.
   - `scope="module", autouse=True`: Runs setup automatically **before the first test in the file**, pauses at `yield`, and executes teardown **after the last test in the file completes**.
   - `scope="session", autouse=True`: Runs setup **once at test suite start** and teardown **once at test suite end**.

---

### 5.3 Summary Comparison: `yield` vs `autouse=True`

| Question | Answered / Controlled By |
| :--- | :--- |
| **"When does setup vs teardown code run?"** | **`yield`** (Before `yield` = setup, after `yield` = teardown). |
| **"Do I have to type the fixture name in test parameters for it to run?"** | **`autouse=True`** (`autouse=True` = No! Runs automatically; `autouse=False` = Yes! Only runs if requested). |

---

### 5.4 Property Matrix: Explicit (`autouse=False`) vs Automatic (`autouse=True`)

| Property | Explicit Fixture (`autouse=False`) | Automatic Fixture (`autouse=True`) |
| :--- | :--- | :--- |
| **Invocation** | Test function **must** declare parameter (`def test_01(cloud_node):`). | Pytest invokes it **automatically** for all tests in scope. |
| **Data Passing** | Can pass returned/yielded objects (`return node` / `yield node`) directly to test. | Typically used for **side effects & teardown hooks** (returns `None` / `yield`). |
| **Use Case** | Host connections, parsed data dicts, client objects. | Environment setups, global log banners, post-success cleanup hooks. |

---

### 5.4 Real-World Project Example ([`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py))

In our framework, the post-success directory cleanup is implemented as an `autouse=True` module fixture inside [`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py):

```python
# tests/test_node_launch.py

@pytest.fixture(scope="module", autouse=True)
def node_launch_cleanup(request, cloud_node: SSHNode, config_data: dict):
    """
    autouse=True guarantees this cleanup hook executes automatically 
    after all tests in test_node_launch.py finish, without requiring 
    test_01 ... test_10 to declare 'node_launch_cleanup' in their parameter lists.
    """
    yield  # Pause while test_01 ... test_10 run
    
    # Teardown Hook: Runs automatically after test_10 finishes
    if hasattr(request.node, "session") and request.session.testsfailed == 0:
        cloud_folder = config_data["CLOUD_NFV_FOLDER"]
        log_info(f"[In-File Cleanup] Deleting CLOUD_NFV_FOLDER '{cloud_folder}' on CLOUD_CLI...")
        loop = get_or_create_event_loop()
        cmd = f"rm -rf '{cloud_folder}' && test ! -d '{cloud_folder}'"
        loop.run_until_complete(cloud_node.execute_and_match(cmd, regex_pattern=r"^", expect_exit_code=0))
```

---

## 6. Factory Fixture Pattern & Type Hint Syntax (`Callable[..., SSHNode]`)

When a fixture returns a **function reference** instead of a static value, it uses the **Factory Pattern**:

```python
# conftest.py
from typing import Callable
from automation_framework.node import SSHNode

@pytest.fixture(scope="session")
def connect_ssh() -> Callable[..., SSHNode]:
    """
    Type Hint Syntax Breakdown:
    - Callable: Returned value is a function reference
    - [...] (Ellipsis): Accepts flexible arguments (connection_str, password, name)
    - SSHNode: Function returns an instance of SSHNode
    """
    def _connect(connection_str: str, password: str, name: str = "Node") -> SSHNode:
        # Opens connection ...
        return node
    return _connect  # Returns function reference without calling it with ()
```

### Passing Arguments to Factory Fixtures:
Inside the test file, when you write `node = connect_ssh("cdot@172.23.1.50", "Cdot@1234")`, Python executes `_connect("cdot@172.23.1.50", "Cdot@1234")` and returns the connected `SSHNode` instance.

---

## 7. Fixture Resolution Priority & Override Hierarchy

When Pytest resolves a fixture name, it searches in order from **most specific (closest to test) to most global**:

```
1. Local Test File (test_*.py)  ──► HIGHEST PRIORITY (WINS!)
2. Immediate Directory conftest.py
3. Parent Directory conftest.py
4. Root Directory conftest.py
5. Built-in / Plugin Fixtures    ──► LOWEST PRIORITY
```

*Rule*: If a fixture with the exact same name exists in both [`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py) and inside [`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py), the **local in-file fixture overrides `conftest.py`**.

---

## 8. Pytest Built-in `request` Introspection Fixture

In Pytest, **`request`** is a built-in special fixture (an instance of `pytest.FixtureRequest`). It provides your fixture functions with **introspection data and metadata** about the running test session, current test module, test function, or command-line parameters.

### 8.1 Core Attribute Reference

| Attribute | What It Provides | Example Use Case |
| :--- | :--- | :--- |
| **`request.session`** | Access to Pytest session object | `request.session.testsfailed` (Count of failed tests in session) |
| **`request.node`** | Access to current test node | `request.node.name` (Name of executing test case) |
| **`request.module`** | Access to current Python test module | `request.module.__name__` (Current test module name) |
| **`request.function`** | Access to current test function | `request.function.__name__` (Current test function name) |
| **`request.config`** | Access to command-line configuration | `request.config.getoption("-m")` (Parsed marker option) |
| **`request.param`** | Access to parameterized fixture data | Used in `@pytest.fixture(params=[...])` |

---

### 8.2 Real-World Project Example ([`tests/test_node_launch.py`](file:///home/bikash/workera/repository/automation_node_launch/tests/test_node_launch.py))

In our framework's `node_launch_cleanup` teardown hook, we use `request` to check if all tests passed (`request.session.testsfailed == 0`) before executing post-success directory deletion:

```python
# tests/test_node_launch.py

@pytest.fixture(scope="module", autouse=True)
def node_launch_cleanup(request, cloud_node: SSHNode, config_data: dict):
    yield  # Wait for test_01 ... test_10 to complete
    
    # Introspect test failure status using 'request'
    if hasattr(request.node, "session") and request.session.testsfailed == 0:
        log_info("[In-File Cleanup] All test steps passed! Deleting CLOUD_NFV_FOLDER...")
        cloud_folder = config_data["CLOUD_NFV_FOLDER"]
        cmd = f"rm -rf '{cloud_folder}' && test ! -d '{cloud_folder}'"
        loop = get_or_create_event_loop()
        loop.run_until_complete(cloud_node.execute_and_match(cmd, regex_pattern=r"^", expect_exit_code=0))
    else:
        log_info("[In-File Cleanup] Test failure detected! Skipping directory cleanup for debugging.")
```

---

### 8.3 Test Function Inspection Example

```python
# Logging current test function name before and after execution
@pytest.fixture(scope="function", autouse=True)
def trace_test_execution(request):
    test_name = request.function.__name__
    print(f"\n[TRACE] Starting test: {test_name}")
    yield
    print(f"[TRACE] Finished test: {test_name}")

---

## 9. Terminal Summary Hook (`pytest_terminal_summary`)

In [`conftest.py`](file:///home/bikash/workera/repository/automation_node_launch/conftest.py), the `pytest_terminal_summary` hook formats custom session completion summary logs:

- **When all marker tests pass (`exitstatus == 0`)**:
  `✔ SUCCESS: All 11 test case(s) passed for marker 'node_launch'!`
- **When any test fails (`exitstatus != 0`)**:
  `✖ FAILURE: Test suite failed for marker 'node_launch' (1 test(s) failed):`
  `   • Failed Test: test_10_edit_creds_cfg_teosm`
```
