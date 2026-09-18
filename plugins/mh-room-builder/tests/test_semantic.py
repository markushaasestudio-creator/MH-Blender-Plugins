import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import cv2
import numpy as np

from mh_room_builder.analyzer.hypotheses import serialize_wall_hypotheses
from mh_room_builder.analyzer.geometry2d import P2
from mh_room_builder.analyzer.ollama_client import chat_structured, is_local_endpoint
from mh_room_builder.analyzer.semantic_review import make_candidate_preview


def test_hypothesis_serialization_keeps_source_and_mm_coordinates():
    raw = [{"start": P2(10, 20), "end": P2(110, 20), "thickness_mm": 120, "confidence": 0.91, "source": "test", "evidence": ["parallel"]}]
    result = serialize_wall_hypotheses(raw, 2.0, prefix="T")
    assert result[0]["id"] == "T0001"
    assert result[0]["start_source"] == [10.0, 20.0]
    assert result[0]["start_mm"] == [20.0, -40.0]
    assert result[0]["end_mm"] == [220.0, -40.0]
    assert result[0]["semantic"]["class"] == "UNKNOWN"


def test_local_endpoint_gate():
    assert is_local_endpoint("http://127.0.0.1:11434")
    assert is_local_endpoint("localhost:11434")
    assert not is_local_endpoint("http://192.168.1.20:11434")


def test_candidate_preview_generation(tmp_path: Path):
    source = tmp_path / "plan.png"
    image = np.full((800, 1200, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (200, 200), (1000, 600), (0, 0, 0), 4)
    cv2.imwrite(str(source), image)
    analysis = {"schema_version": "0.1.2", "source": {"path": str(source), "page": 1, "kind": "raster"}, "preview_path": str(source), "stats": {"preview_scale_from_source": 1.0}, "wall_hypotheses": [{"id": "R0001", "start_source": [200, 200], "end_source": [1000, 200], "start_mm": [200, -200], "end_mm": [1000, -200], "thickness_mm": 120, "geometry_confidence": 0.9, "source": "test", "evidence": []}]}
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    output = tmp_path / "preview.png"
    result = make_candidate_preview(str(analysis_path), "R0001", str(output))
    assert result["candidate_id"] == "R0001"
    assert output.exists()
    rendered = cv2.imread(str(output))
    assert rendered is not None
    assert rendered.shape[0] == 430
    assert rendered.shape[1] == 640


class _MockOllamaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        if self.path == "/api/show":
            body = {"capabilities": ["completion", "vision"]}
        elif self.path == "/api/chat":
            assert payload["stream"] is False
            assert payload["messages"][-1]["images"]
            assert isinstance(payload["format"], dict)
            content = json.dumps({"results": [{"candidate_id": "R0001", "class": "WALL", "confidence": 0.88, "structural_boundary": True, "rationale": "mock"}]})
            body = {"message": {"content": content}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return


def test_structured_ollama_vision_request(tmp_path: Path):
    server = HTTPServer(("127.0.0.1", 0), _MockOllamaHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        image_path = tmp_path / "image.png"
        cv2.imwrite(str(image_path), np.full((20, 20, 3), 255, dtype=np.uint8))
        schema = {"type": "object", "properties": {"results": {"type": "array"}}, "required": ["results"]}
        parsed, _raw = chat_structured(f"http://127.0.0.1:{server.server_port}", "qwen-test", "classify", [image_path], schema, timeout=10)
        assert parsed["results"][0]["class"] == "WALL"
    finally:
        server.shutdown()
        thread.join(timeout=2)
