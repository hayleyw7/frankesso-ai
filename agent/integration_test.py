"""Run actual local-model tests against synthetic fixtures only; no external traffic."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import zipfile

import agent
from run_agent import LocalServer


def main():
    project = Path(sys.argv[1])
    real_connect = socket.socket.connect
    addresses = []
    def local_only(sock, address):
        if address[0] != "127.0.0.1" or address[1] != agent.PORT:
            raise RuntimeError("Test blocked a non-model network destination")
        addresses.append(address)
        return real_connect(sock, address)
    socket.socket.connect = local_only
    report = {"tests": [], "external_requests": 0}
    try:
        with LocalServer(project), tempfile.TemporaryDirectory(prefix="agent-model-test-") as root:
            fixture = Path(root) / "fixture.txt"
            fixture.write_text("The test code is APRICOT-527.\n", encoding="utf-8")
            decisions = []
            def deny(action, details):
                decisions.append(action)
                return False
            controller = agent.Controller(root, deny)
            result = controller.turn("Use read_file to read fixture.txt and tell me the exact test code inside it.")
            assert any(x["tool"] == "read_file" and x["ok"] for x in controller.audit), controller.audit
            assert "APRICOT-527" in result, result
            report["tests"].append({"name": "actual_model_read_file", "passed": True, "response": result})
            controller.audit.clear()
            result = controller.turn("Use write_file to replace fixture.txt with exactly CHANGED. Ask the tool to do this now.")
            assert any(x["tool"] == "write_file" and x.get("denied") for x in controller.audit), controller.audit
            assert fixture.read_text() == "The test code is APRICOT-527.\n"
            report["tests"].append({"name": "actual_model_write_denied", "passed": True, "response": result})
            controller.audit.clear()
            with zipfile.ZipFile(Path(root) / "fixture.docx", "w") as document:
                document.writestr("word/document.xml", "<document><p><r><t>Document code: PLUM-819</t></r></p></document>")
            result = controller.turn("Use read_document to read fixture.docx and tell me the exact document code.")
            assert any(x["tool"] == "read_document" and x["ok"] for x in controller.audit), controller.audit
            assert "PLUM-819" in result, result
            report["tests"].append({"name": "actual_model_read_docx", "passed": True, "response": result})
            controller.audit.clear()
            controller.web_mode = "ask_each_request"
            result = controller.turn("Use web_search now with query 'Python official documentation'. The controller approval prompt will decide permission.")
            assert any(x["tool"] == "web_search" and x.get("denied") for x in controller.audit), controller.audit
            report["tests"].append({"name": "actual_model_real_web_denied_before_network", "passed": True, "response": result})
            report["approval_prompts"] = decisions
            report["controller_network_destinations"] = sorted(set(str(a) for a in addresses))
            print(json.dumps(report, indent=2))
    finally:
        socket.socket.connect = real_connect


if __name__ == "__main__":
    main()
