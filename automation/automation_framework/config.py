import os
from typing import Dict, Optional

class ConfigParser:
    """Simple and easy key=value configuration file parser."""
    
    @staticmethod
    def parse(file_path: str) -> Dict[str, str]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
        config = {}
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    config[key] = val
        return config

    @staticmethod
    def get_host_credentials(connection_str: str, default_port: int = 22):
        """Helper to parse connection strings like 'username@hostname:port' or 'user@host'."""
        user_host = connection_str.split(':')
        port = int(user_host[1]) if len(user_host) > 1 else default_port
        user_and_host = user_host[0]
        if '@' in user_and_host:
            username, hostname = user_and_host.split('@', 1)
        else:
            username, hostname = None, user_and_host
        return username, hostname, port
