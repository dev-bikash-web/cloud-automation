import logging
import sys
import os
import re
import pytest

class ANSIColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ColorFormatter(logging.Formatter):
    """Console formatter with ANSI color codes (keeps live log untouched)."""
    def format(self, record):
        log_fmt = '%(asctime)s - [%(levelname)s] - %(message)s'
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

class FileLogFormatter(logging.Formatter):
    """File log formatter: Injects active test function name and retains ANSI color codes for file logs."""
    def format(self, record):
        current = os.environ.get("PYTEST_CURRENT_TEST", "")
        test_prefix = ""
        if current:
            test_part = current.split("::")[-1].split(" ")[0]
            test_prefix = f"[{test_part}] "
        
        msg = record.getMessage()
        log_fmt = f'%(asctime)s - [%(levelname)s] - {test_prefix}{msg}'
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def get_test_file_log_name(default_name: str = "execution.log") -> str:
    """Helper to detect active test file stem (e.g., 'test_node_launch_execution.log')."""
    current = os.environ.get("PYTEST_CURRENT_TEST", "")
    if current:
        file_part = current.split("::")[0]
        basename = os.path.basename(file_part)
        stem = os.path.splitext(basename)[0]
        if stem:
            return f"{stem}_execution.log"
    return default_name

class DynamicFileHandler(logging.FileHandler):
    """FileHandler that lazily routes logs to <test_file>_execution.log based on active test suite."""
    def __init__(self, default_filename: str = "execution.log", encoding: str = 'utf-8'):
        self.default_filename = default_filename
        self.active_filename = None
        super().__init__(default_filename, encoding=encoding, delay=True)

    def emit(self, record):
        target = get_test_file_log_name(self.default_filename)
        if target != self.active_filename:
            if self.stream is not None:
                self.close()
            self.baseFilename = os.path.abspath(target)
            self.active_filename = target
        super().emit(record)

def setup_logger(name: str = "automation", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        # 1. Console Handler (Live Log - untouched)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColorFormatter())
        logger.addHandler(console_handler)

        # 2. File Log Handler (Dynamic prefix file name & test function prefix)
        file_handler = DynamicFileHandler("execution.log", encoding='utf-8')
        file_handler.setFormatter(FileLogFormatter())
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()

def log_info(msg: str):
    logger.info(f"{ANSIColors.OKCYAN}{msg}{ANSIColors.ENDC}")

def log_success(msg: str):
    logger.info(f"{ANSIColors.OKGREEN}✔ SUCCESS: {msg}{ANSIColors.ENDC}")

def log_error(msg: str):
    logger.error(f"{ANSIColors.FAIL}✖ ERROR: {msg}{ANSIColors.ENDC}")

def log_step(step_num: int, title: str):
    msg = f"\n>>> STEP {step_num}: {title}"
    logger.info(f"{ANSIColors.BOLD}{ANSIColors.HEADER}{msg}{ANSIColors.ENDC}")

def test_pass(msg: str):
    """Logs green success checkmark message."""
    log_success(msg)

def test_fail(msg: str):
    """Logs red error crossmark message and fails Pytest test case immediately."""
    log_error(msg)
    pytest.fail(msg)
