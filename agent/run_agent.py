"""Start an isolated CPU model server for the agent; preserve the ordinary chat server."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import agent


def server_environment(source=None):
    # Prevent inherited llama.cpp variables from silently enabling tools, MCP or remote settings.
    return {key: value for key, value in (os.environ if source is None else source).items()
            if not key.upper().startswith("LLAMA_ARG_")}


class LocalServer:
    def __init__(self, project, stop=None, model_path=None, startup_timeout=120, skip_warmup=False, threads=6):
        self.project = Path(project)
        self.process = None
        self.stop = stop
        self.startup_timeout = startup_timeout
        self.skip_warmup = skip_warmup
        self.threads = threads
        self.startup_log = ""
        self.model_path = model_path or self.project / "models" / "Qwen3-4B-Q4_K_M.gguf"

    def __enter__(self):
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", agent.PORT)) == 0:
                raise RuntimeError("Agent port 18081 is already in use; no process was changed.")
        self.logs = tempfile.TemporaryDirectory(prefix="local-agent-server-")
        self.log_path = Path(self.logs.name) / "server.log"
        self.log = self.log_path.open("w", encoding="utf-8")
        args = [str(self.project / "runner" / "llama-server.exe"), "-m",
                str(self.model_path),
                "--alias", "local-qwen", "--host", "127.0.0.1", "--port", str(agent.PORT),
                "--cors-origins", "localhost",
                "--offline", "--no-agent", "--no-ui-mcp-proxy", "--no-ui",
                "-c", "4096", "-np", "1", "--device", "none", "-ngl", "0",
                "--no-op-offload", "-t", str(self.threads), "--jinja", "--reasoning", "off"]
        if self.skip_warmup:
            args.append("--no-warmup")
        try:
            self.process = subprocess.Popen(args, cwd=self.project, stdout=self.log, stderr=self.log, env=server_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            last_health = "no response"
            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                if self.stop is not None and self.stop.is_set():
                    raise RuntimeError("Startup canceled.")
                if self.process.poll() is not None:
                    raise RuntimeError(f"Agent server exited ({self.process.returncode}); existing chat configuration was not changed.")
                connection = http.client.HTTPConnection("127.0.0.1", agent.PORT, timeout=2)
                try:
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    response.read(512)
                    last_health = f"HTTP {response.status}"
                    if response.status == 200:
                        return self
                    if response.status != 503:
                        raise RuntimeError(f"Local model returned unexpected health status: {last_health}.")
                except (OSError, http.client.HTTPException) as error:
                    last_health = type(error).__name__
                finally:
                    connection.close()
                if self.stop is not None:
                    self.stop.wait(1)
                else:
                    time.sleep(1)
            raise RuntimeError(f"Agent server was not ready after {self.startup_timeout}s ({last_health}).")
        except BaseException:
            self._cleanup(capture_startup=True)
            raise

    def log_tail(self, limit=8192):
        with self.log_path.open("rb") as log:
            log.seek(max(0, self.log_path.stat().st_size - limit))
            return log.read(limit).decode("utf-8", errors="replace")

    def cancel(self):
        """Interrupt only this instance; the owning thread reaps the process."""
        if self.stop is not None:
            self.stop.set()
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass

    def __exit__(self, *_):
        self._cleanup()

    def _cleanup(self, capture_startup=False):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()
        if capture_startup:
            # Failure is before accepting user prompts. Keep only a small tail
            # for package smoke tests, outside the ordinary chat transcript.
            try:
                self.startup_log = self.log_tail()
            except OSError:
                pass
        self.logs.cleanup()


def read_config():
    config_path = Path(__file__).parent / "access.json"
    if not config_path.exists():
        config_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Frankesso" / "access.json"
    return json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {
        "approved_local_roots": [], "web_mode": "ask_each_request",
    }


def runtime_root(config):
    return Path(config.get("runtime_root") or Path(__file__).resolve().parent.parent)


if __name__ == "__main__":
    try:
        config = read_config()
        project = runtime_root(config)
        with LocalServer(project):
            agent.main(approved_roots=config["approved_local_roots"], web_mode=config.get("web_mode", "mock"), private_skills_root=config.get("private_skills_root"))
    except (OSError, RuntimeError) as error:
        print(str(error))
        raise SystemExit(1)
