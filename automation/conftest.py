import os
import asyncio
import pytest
from typing import Dict, Callable, Tuple, Optional

from automation_framework.config import ConfigParser
from automation_framework.node import SSHNode
from automation_framework.logger import log_info, test_pass as logger_test_pass, test_fail as logger_test_fail

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Helper to retrieve or create an active asyncio event loop."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

@pytest.fixture(scope="module")
def config_data(request) -> Dict[str, str]:
    """
    Module-scoped fixture dynamically locating variables.txt in the directory
    of the executing test module file. If missing, traverses parent directories.
    """
    test_file_path = str(request.path) if hasattr(request, "path") else str(request.fspath)
    test_dir = os.path.dirname(os.path.abspath(test_file_path))
    base_dir = os.path.dirname(os.path.abspath(__file__))

    curr_dir = test_dir
    var_file = None

    while True:
        candidate = os.path.join(curr_dir, "variables.txt")
        if os.path.exists(candidate):
            var_file = candidate
            break
        if curr_dir == base_dir or curr_dir == os.path.dirname(curr_dir):
            break
        curr_dir = os.path.dirname(curr_dir)

    if not var_file:
        raise FileNotFoundError(
            f"Configuration file 'variables.txt' missing from test directory '{test_dir}' and ancestor paths."
        )

    abs_var_file = os.path.abspath(var_file)
    log_info(f"✔ RESOLVED CONFIGURATION FILE FOR '{os.path.basename(test_file_path)}': '{abs_var_file}'")

    parsed = ConfigParser.parse(abs_var_file)
    parsed["_CONFIG_FILE_PATH"] = abs_var_file
    return parsed

@pytest.fixture(scope="session")
def parse_credentials() -> Callable[[str, int], Tuple[Optional[str], Optional[str], int]]:
    """Generic wrapper fixture for parsing host credential strings ('user@host:port')."""
    return ConfigParser.get_host_credentials

@pytest.fixture(scope="session")
def connect_ssh() -> Callable[..., SSHNode]:
    """
    Unified abstract factory fixture to connect to ANY remote SSH host on demand.
    Supports both direct SSH connections and Jump Server (proxy host) connections.

    Accepts:
      connection_str: "user@host:port" or "user@host"
      password: "target_password"
      jump_connection_str: Optional "jump_user@jump_host:port"
      jump_password: Optional "jump_password"
      name: Optional display name for node (default "Node")
      timeout: Optional global timeout in seconds (default 600)
    """
    def _connect(
        connection_str: str,
        password: str,
        jump_connection_str: Optional[str] = None,
        jump_password: Optional[str] = None,
        name: str = "Node",
        timeout: int = 600
    ) -> SSHNode:
        user, host, port = ConfigParser.get_host_credentials(connection_str)

        jump_user, jump_host, jump_port = None, None, 22
        if jump_connection_str:
            jump_user, jump_host, jump_port = ConfigParser.get_host_credentials(jump_connection_str, 22)

        node = SSHNode(
            hostname=host,
            username=user,
            password=password,
            port=port,
            name=name,
            global_timeout=timeout,
            jump_hostname=jump_host,
            jump_username=jump_user,
            jump_password=jump_password,
            jump_port=jump_port
        )
        loop = get_or_create_event_loop()
        loop.run_until_complete(node.connect())
        return node
    return _connect

@pytest.fixture(scope="session")
def close_ssh() -> Callable[[SSHNode], None]:
    """
    Generic wrapper fixture to close any SSHNode connection cleanly on demand.
    Accepts: (node: SSHNode) -> None
    """
    def _close(node: SSHNode) -> None:
        if node:
            loop = get_or_create_event_loop()
            loop.run_until_complete(node.close())
    return _close

@pytest.fixture(scope="session")
def test_pass() -> Callable[[str], None]:
    """Session-scoped fixture providing test_pass(msg) helper."""
    return logger_test_pass

@pytest.fixture(scope="session")
def test_fail() -> Callable[[str], None]:
    """Session-scoped fixture providing test_fail(msg) helper."""
    return logger_test_fail

def pytest_runtest_setup(item):
    """Lifecycle hook: Emits PRE-TEST SETUP log header."""
    log_info(" PRE-TEST SETUP ".center(60, "="))

def pytest_runtest_call(item):
    """Lifecycle hook: Emits TEST CASE EXECUTION log header."""
    log_info(" TEST CASE EXECUTION ".center(60, "="))

def pytest_runtest_teardown(item):
    """Lifecycle hook: Emits POST-TEST CLEANUP log header."""
    log_info(" POST-TEST CLEANUP ".center(60, "="))

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Session completion hook: Outputs custom marker summary logs.
    Shows green success summary when all marker tests pass, or lists failing test names.
    """
    markexpr = config.option.markexpr or "all"
    stats = terminalreporter.stats
    
    passed_reports = stats.get('passed', [])
    failed_reports = stats.get('failed', [])
    
    terminalreporter.write_sep("=", "AUTOMATION SUITE EXECUTION SUMMARY", bold=True, cyan=True)
    
    if exitstatus == 0:
        num_passed = len(passed_reports)
        msg = f"✔ SUCCESS: All {num_passed} test case(s) passed for marker '{markexpr}'!"
        terminalreporter.write_line(msg, green=True, bold=True)
    else:
        num_failed = len(failed_reports)
        msg = f"✖ FAILURE: Test suite failed for marker '{markexpr}' ({num_failed} test(s) failed):"
        terminalreporter.write_line(msg, red=True, bold=True)
        for rep in failed_reports:
            test_name = rep.nodeid.split("::")[-1]
            terminalreporter.write_line(f"   • Failed Test: {test_name} [{rep.nodeid}]", red=True)
            
    terminalreporter.write_sep("=", "", cyan=True)
