"""
Automation Framework - A modular and easy-to-use Python framework for remote node SSH/SFTP automation.
"""

from .config import ConfigParser
from .node import SSHNode
from .pipeline import PipelineEngine, Step, step_action
from .logger import setup_logger, log_info, log_success, log_error, log_step

__all__ = [
    "ConfigParser",
    "SSHNode",
    "PipelineEngine",
    "Step",
    "step_action",
    "setup_logger",
    "log_info",
    "log_success",
    "log_error",
    "log_step",
]
