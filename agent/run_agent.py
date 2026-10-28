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
    def __init__(self, project):
        self.project = Path(project)
        self.process = None

    def __enter__(self):
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", agent.PORT)) == 0:
                raise RuntimeError("Agent port 18081 is already in use; no process was changed.")
        self.logs = tempfile.TemporaryDirectory(prefix="local-agent-server-")
        self.log = (Path(self.logs.name) / "server.log").open("w", encoding="utf-8")
        args = [str(self.project / "runner" / "llama-server.exe"), "-m",
                str(self.project / "models" / "Qwen3-4B-Q4_K_M.gguf"),
                "--alias", "local-qwen", "--host", "127.0.0.1", "--port", str(agent.PORT),
                "--cors-origins", "localhost",
                "--offline", "--no-agent", "--no-ui-mcp-proxy", "--no-ui",
                "-c", "4096", "-np", "1", "--device", "none", "-ngl", "0",
                "--no-op-offload", "-t", "6", "--jinja", "--reasoning", "off"]
        try:
            self.process = subprocess.Popen(args, cwd=self.project, stdout=self.log, stderr=self.log, env=server_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for _ in range(120):
                if self.process.poll() is not None:
                    raise RuntimeError("Agent server exited; existing chat configuration was not changed.")
                connection = http.client.HTTPConnection("127.0.0.1", agent.PORT, timeout=2)
                try:
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    response.read()
                    if response.status == 200:
                        return self
                except OSError:
                    pass
                finally:
                    connection.close()
                time.sleep(1)
            raise RuntimeError("Agent server did not become ready within two minutes")
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()
        self.logs.cleanup()


if __name__ == "__main__":
    try:
        config_path = Path(__file__).parent / "access.json"
        if not config_path.exists():
            config_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Frankesso" / "access.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {"approved_local_roots": [], "web_mode": "ask_each_request"}
        project = config.get("runtime_root") or Path(__file__).resolve().parent.parent
        with LocalServer(project):
            agent.main(approved_roots=config["approved_local_roots"], web_mode=config.get("web_mode", "mock"), private_skills_root=config.get("private_skills_root"))
    except (OSError, RuntimeError) as error:
        print(str(error))
        raise SystemExit(1)
