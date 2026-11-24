from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

import local_only


class LocalOnlyTests(unittest.TestCase):
    def test_windows_guard_rejects_network_paths_before_io(self):
        with patch.object(local_only.sys, "platform", "win32"):
            with patch.object(local_only, "windows_drive_type", return_value=4) as drive:
                for path in ("\\\\fixture.invalid\\share\\model.gguf", "https://fixture.invalid/model.gguf",
                             "\\\\?\\UNC\\fixture.invalid\\share\\model.gguf"):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        local_only.require_local_path(path)
                drive.assert_not_called()
                with self.assertRaisesRegex(ValueError, "Network drives"):
                    local_only.require_local_path("Z:\\model.gguf")
                drive.assert_called_once_with("Z:\\")

    def test_socket_guard_blocks_external_attempts_but_allows_actual_model_request(self):
        # A child process is isolated because audit hooks intentionally cannot be removed.
        script = textwrap.dedent("""
            import agent, http.server, socket, socketserver, threading
            from local_only import install_socket_guard

            class Model(http.server.BaseHTTPRequestHandler):
                def do_POST(self):
                    assert self.path == '/v1/chat/completions'
                    self.rfile.read(int(self.headers['Content-Length']))
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"choices":[{"message":{"content":"A fern."}}]}')

            class FixtureServer(http.server.HTTPServer):
                def server_bind(self):
                    # HTTPServer.server_bind resolves a hostname even for a loopback
                    # fixture, which can stall on macOS if reverse DNS is unavailable.
                    socketserver.TCPServer.server_bind(self)
                    self.server_name, self.server_port = self.server_address[:2]

            with FixtureServer(('127.0.0.1', 0), Model) as server:
                server.timeout = 3
                agent.PORT = server.server_port
                with socket.socket() as s:
                    install_socket_guard(agent.PORT)
                    for attempt in (lambda: s.connect(('192.0.2.1', 443)),
                                    lambda: s.connect_ex(('192.0.2.1', 443)),
                                    lambda: s.sendto(b'fixture', ('192.0.2.1', 53)),
                                    lambda: socket.getaddrinfo('fixture.invalid', 443),
                                    lambda: s.connect(('127.0.0.1', 443))):
                        try:
                            attempt()
                        except PermissionError:
                            continue
                        raise AssertionError('An external socket attempt reached the OS')
                thread = threading.Thread(target=server.handle_request, daemon=True)
                thread.start()
                assert agent.model_request([{'role':'user', 'content':'Say a plant.'}]) == {'content':'A fern.'}
                thread.join(3)
                assert not thread.is_alive()
        """)
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).parent,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_configuration_cannot_restore_the_web_tool(self):
        import agent
        import run_agent
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            config_path = Path(folder, "access.json")
            config_path.write_text('{"web_mode":"ask_each_request", "approved_local_roots":[]}',
                                   encoding="utf-8")
            with patch.object(run_agent, "__file__", str(Path(folder, "run_agent.py"))):
                config = run_agent.read_config()
            controller = agent.Controller(folder, approved_roots=config["approved_local_roots"])
            self.assertIn("Unknown tool", controller.execute("web_search", {"query":"test"})["error"])
