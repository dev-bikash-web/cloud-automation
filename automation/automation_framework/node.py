import os
import re
import asyncio
import paramiko
from typing import Dict, Any, Optional
from .logger import log_info, log_error, log_success

class SSHNode:
    """
    Direct Lightweight SSH Node Client.
    Exposes direct SSH execution, SFTP channel, and synchronous helper wrappers.
    """

    DEFAULT_GLOBAL_TIMEOUT: int = 300

    def __init__(
        self,
        hostname: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: int = 22,
        name: str = "Node",
        global_timeout: int = DEFAULT_GLOBAL_TIMEOUT,
        jump_hostname: Optional[str] = None,
        jump_username: Optional[str] = None,
        jump_password: Optional[str] = None,
        jump_port: int = 22,
        jump_chain: Optional[list] = None
    ):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.name = name
        self.global_timeout = global_timeout
        self.jump_hostname = jump_hostname
        self.jump_username = jump_username
        self.jump_password = jump_password
        self.jump_port = jump_port
        self.jump_chain = jump_chain or []
        
        self.client: Optional[paramiko.SSHClient] = None
        self.jump_client: Optional[paramiko.SSHClient] = None
        self.jump_channel: Optional[paramiko.Channel] = None
        self.jump_clients: list = []
        self.jump_channels: list = []
        self.sftp: Optional[paramiko.SFTPClient] = None

    @staticmethod
    def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
        """Helper to retrieve active event loop or create a new one safely."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def connect(
        self,
        hostname: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Connect SSH and initialize direct SFTP handle."""
        if hostname:
            self.hostname = hostname
        if username:
            self.username = username
        if password:
            self.password = password
        if port:
            self.port = port

        if not self.hostname or not self.username:
            raise ValueError(f"[{self.name}] Hostname and username must be specified to connect.")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._connect_sync, timeout)
        return {
            "exit_code": 0,
            "stdout": f"Connected to {self.name} ({self.username}@{self.hostname}:{self.port})",
            "stderr": ""
        }

    def _connect_sync(self, timeout: int):
        sock_channel = None
        if self.jump_chain:
            curr_sock = None
            for i, jump in enumerate(self.jump_chain):
                j_host = jump.get("hostname")
                j_user = jump.get("username")
                j_pass = jump.get("password")
                j_port = jump.get("port", 22)
                
                log_info(f"Connecting to Jump Server Hop {i+1} ({j_user}@{j_host}:{j_port})...")
                j_client = paramiko.SSHClient()
                j_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                j_client.connect(
                    hostname=j_host,
                    port=j_port,
                    username=j_user,
                    password=j_pass,
                    sock=curr_sock,
                    timeout=timeout,
                    banner_timeout=60
                )
                self.jump_clients.append(j_client)
                
                next_dest = (
                    (self.jump_chain[i+1]["hostname"], self.jump_chain[i+1].get("port", 22))
                    if i + 1 < len(self.jump_chain)
                    else (self.hostname, self.port)
                )
                
                log_info(f"Opening SSH proxy channel from Hop {i+1} ({j_host}) to Next Hop ({next_dest[0]}:{next_dest[1]})...")
                j_transport = j_client.get_transport()
                curr_sock = j_transport.open_channel("direct-tcpip", next_dest, (j_host, j_port))
                self.jump_channels.append(curr_sock)
                
            sock_channel = curr_sock
        elif self.jump_hostname and self.jump_username:
            log_info(f"Connecting to Jump Server ({self.jump_username}@{self.jump_hostname}:{self.jump_port})...")
            self.jump_client = paramiko.SSHClient()
            self.jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.jump_client.connect(
                hostname=self.jump_hostname,
                port=self.jump_port,
                username=self.jump_username,
                password=self.jump_password,
                timeout=timeout,
                banner_timeout=60
            )
            log_info(f"Opening SSH proxy channel via Jump Server to Target ({self.username}@{self.hostname}:{self.port})...")
            jump_transport = self.jump_client.get_transport()
            sock_channel = jump_transport.open_channel(
                "direct-tcpip",
                (self.hostname, self.port),
                (self.jump_hostname, self.jump_port)
            )
            self.jump_channel = sock_channel
        else:
            log_info(f"Connecting to {self.name} ({self.username}@{self.hostname}:{self.port})...")

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            sock=sock_channel,
            timeout=timeout,
            banner_timeout=60
        )
        self.sftp = self.client.open_sftp()
        log_success(f"Connected to {self.name}")

    async def close(self) -> Dict[str, Any]:
        """Close connections."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._close_sync)
        return {"exit_code": 0, "stdout": f"Closed connection to {self.name}", "stderr": ""}

    def _close_sync(self):
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        for chan in reversed(self.jump_channels):
            try:
                chan.close()
            except Exception:
                pass
        for cli in reversed(self.jump_clients):
            try:
                cli.close()
            except Exception:
                pass
        if self.jump_channel:
            try:
                self.jump_channel.close()
            except Exception:
                pass
        if self.jump_client:
            try:
                self.jump_client.close()
            except Exception:
                pass
        log_info(f"Closed connection to {self.name}")

    async def run_cmd(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        pty: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a remote shell command directly and return:
        {"exit_code": int, "stdout": str, "stderr": str}
        """
        effective_timeout = timeout if timeout is not None else self.global_timeout
        loop = asyncio.get_running_loop()
        exit_code, stdout, stderr = await loop.run_in_executor(
            None, self._run_cmd_sync, command, cwd, effective_timeout, pty
        )
        
        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        }

    def exec_cmd(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        pty: bool = True
    ) -> Dict[str, Any]:
        """Synchronous wrapper around run_cmd that automatically handles the asyncio event loop."""
        loop = self._get_or_create_event_loop()
        return loop.run_until_complete(self.run_cmd(command, cwd=cwd, timeout=timeout, pty=pty))

    def _run_cmd_sync(self, command: str, cwd: Optional[str], timeout: int, pty: bool) -> tuple:
        if not self.client:
            raise RuntimeError(f"Node {self.name} is not connected.")
        
        full_cmd = f"cd '{cwd}' && {command}" if cwd else command
        log_info(f"[{self.name}] Executing (timeout={timeout}s): {full_cmd}")
        
        stdin, stdout, stderr = self.client.exec_command(full_cmd, timeout=timeout, get_pty=pty)
        
        out_str = stdout.read().decode('utf-8', errors='replace')
        err_str = stderr.read().decode('utf-8', errors='replace')
        exit_code = stdout.channel.recv_exit_status()
        
        return exit_code, out_str, err_str

    async def execute_and_match(
        self,
        command: str,
        regex_pattern: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        pty: bool = True,
        expect_exit_code: int = 0
    ) -> Dict[str, Any]:
        """
        Execute command on node directly, compare output against regex pattern,
        and return {"match": bool, "stdout": str, "stderr": str}.
        """
        res = await self.run_cmd(command, cwd=cwd, timeout=timeout, pty=pty)
        exit_code = res["exit_code"]
        stdout = res["stdout"]
        stderr = res["stderr"]
        combined_output = stdout + ("\n" + stderr if stderr else "")

        matched = bool(re.search(regex_pattern, combined_output, re.MULTILINE | re.DOTALL))
        exit_code_ok = (exit_code == expect_exit_code)
        overall_match = matched and exit_code_ok

        if not exit_code_ok:
            log_error(f"[{self.name}] Exit code mismatch: got {exit_code}, expected {expect_exit_code}")

        if not matched:
            log_error(f"[{self.name}] Regex pattern '{regex_pattern}' failed to match output!\n--- Output Start ---\n{combined_output}\n--- Output End ---")
        else:
            log_success(f"[{self.name}] Command succeeded & matched regex pattern: '{regex_pattern}'")

        return {
            "match": overall_match,
            "stdout": stdout,
            "stderr": stderr
        }

    def exec_and_match(
        self,
        command: str,
        regex_pattern: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        pty: bool = True,
        expect_exit_code: int = 0
    ) -> Dict[str, Any]:
        """Synchronous wrapper around execute_and_match that automatically handles the asyncio event loop."""
        loop = self._get_or_create_event_loop()
        return loop.run_until_complete(
            self.execute_and_match(
                command=command,
                regex_pattern=regex_pattern,
                cwd=cwd,
                timeout=timeout,
                pty=pty,
                expect_exit_code=expect_exit_code
            )
        )
