"""Small standard-library API stub for exercising the frontend before FastAPI exists.

Run from the repository root:
    python3 tests/frontend/mock_api.py --scenario completed_with_warnings

Open http://127.0.0.1:8081, set the API base URL to that origin, and submit either
input mode. This server only returns illustrative fixture data from frontend/.
"""

from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
MOCK_RESULT = json.loads((FRONTEND / "mock_research_result.json").read_text())
RUN_ID = "mock-run-001"


class MockState:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.run_input = {}
        self.poll_count = 0
        self.lock = threading.Lock()

    def get_status(self):
        with self.lock:
            self.poll_count += 1
            if self.poll_count == 1:
                return {"run_id": RUN_ID, "status": "queued", "warnings": []}
            if self.poll_count == 2:
                return {"run_id": RUN_ID, "status": "running", "current_stage": "retrieval", "warnings": []}
            if self.poll_count == 3:
                return {"run_id": RUN_ID, "status": "running", "current_stage": "verification", "warnings": []}
            return {"run_id": RUN_ID, "status": self.scenario, "current_stage": "report", "warnings": self._scenario_warnings()}

    def _scenario_warnings(self):
        if self.scenario == "completed_with_warnings":
            return ["Mock API scenario: completed with warnings; content is illustrative."]
        if self.scenario == "failed":
            return ["Mock API scenario: one workflow node failed; available result is partial."]
        return []

    def result(self):
        result = json.loads(json.dumps(MOCK_RESULT))
        result["run_id"] = RUN_ID
        result["status"] = self.scenario
        request = self.run_input
        if request.get("question"):
            result["question"] = request["question"]
        if request.get("company_name"):
            result.setdefault("company", {})["name"] = request["company_name"]
        result["mock_data"] = True
        result["mock_notice"] = "Local mock API fixture only. No company research or verification was performed."
        if self.scenario == "completed":
            result["warnings"] = []
            result["failed_nodes"] = []
        elif self.scenario == "failed":
            result["failed_nodes"] = [
                {"node": "mock_verification", "status": "failed", "reason": "This fixture simulates a workflow failure."}
            ]
            result["partial_results_summary"] = "The local mock API returned a partial fixture to exercise the failed-run UI."
        return result


class Handler(BaseHTTPRequestHandler):
    server_version = "FrontendContractMock/1.0"

    @property
    def state(self) -> MockState:
        return self.server.mock_state  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):
        print("[mock-api] " + fmt % args)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            return self.send_json({"status": "ok"})
        if path == f"/api/runs/{RUN_ID}":
            return self.send_json(self.state.get_status())
        if path == f"/api/runs/{RUN_ID}/result":
            return self.send_json(self.state.result())
        if path.startswith("/api/"):
            return self.send_json({"detail": "Mock API route not found"}, 404)
        return self.serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/company/discover":
            payload = self.read_json()
            sources = [
                {"document_id": item.get("document_id"), "filename": item.get("filename"), "status": "mock_available"}
                for item in MOCK_RESULT.get("evidence_items", [])
            ]
            return self.send_json({"sources": sources, "warnings": []})
        if path == "/api/documents/upload":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("latin-1", errors="replace")
            names = re.findall(r'filename="([^"]+)"', body)
            if not names:
                return self.send_json({"detail": "No upload filename found in mock request"}, 400)
            documents = [
                {"document_id": f"mock-upload-{index:03d}", "filename": name, "status": "uploaded", "warnings": []}
                for index, name in enumerate(names, 1)
            ]
            return self.send_json({"documents": documents})
        if path == "/api/runs":
            payload = self.read_json()
            with self.state.lock:
                self.state.run_input = payload
                self.state.poll_count = 0
            return self.send_json({"run_id": RUN_ID, "status": "queued"}, 202)
        return self.send_json({"detail": "Mock API route not found"}, 404)

    def serve_static(self, request_path):
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        candidate = (FRONTEND / relative).resolve()
        if FRONTEND.resolve() not in candidate.parents and candidate != FRONTEND.resolve():
            return self.send_json({"detail": "Not found"}, 404)
        if not candidate.is_file():
            return self.send_json({"detail": "Not found"}, 404)
        content_type = "text/plain; charset=utf-8"
        if candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif candidate.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Serve the frontend and a local API contract stub.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--scenario", choices=("completed", "completed_with_warnings", "failed"), default="completed_with_warnings")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.mock_state = MockState(args.scenario)
    print(f"Frontend + mock API: http://{args.host}:{args.port} (scenario={args.scenario})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local frontend mock API.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
