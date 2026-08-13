import os
import asyncio
import pytest
from typing import Dict, Callable, Tuple, Optional

from automation_framework.config import ConfigParser
from automation_framework.node import SSHNode
from automation_framework.logger import test_pass as logger_test_pass, test_fail as logger_test_fail

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Helper to retrieve or create an active asyncio event loop."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

@pytest.fixture(scope="session")
def config_data() -> Dict[str, str]:
    """
    Session-scoped fixture parsing variables.txt ONCE per test run.
    Provides cached configuration dictionary to any test case on demand.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    var_file = os.path.join(base_dir, "variables.txt")
    if not os.path.exists(var_file):
        raise FileNotFoundError(f"Configuration file missing: {var_file}")
    
    return ConfigParser.parse(var_file)

@pytest.fixture(scope="session")
def parse_credentials() -> Callable[[str, int], Tuple[Optional[str], Optional[str], int]]:
    """Generic wrapper fixture for parsing host credential strings ('user@host:port')."""
    return ConfigParser.get_host_credentials

@pytest.fixture(scope="session")
def connect_ssh() -> Callable[..., SSHNode]:
    """
    Generic factory wrapper fixture to connect to ANY remote SSH host on demand.
    Accepts: (connection_str, password, name="Node", timeout=600) -> SSHNode
    """
    def _connect(connection_str: str, password: str, name: str = "Node", timeout: int = 600) -> SSHNode:
        user, host, port = ConfigParser.get_host_credentials(connection_str)
        node = SSHNode(
            hostname=host,
            username=user,
            password=password,
            port=port,
            name=name,
            global_timeout=timeout
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
