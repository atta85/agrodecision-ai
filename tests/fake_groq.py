"""A tiny local imitation of Groq's chat-completions endpoint for offline testing.

It is STRICT like the real service: any message key other than role/content/name is rejected with the same
error text Groq returned to us ("property 'cache_breakpoint' is unsupported")."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ALLOWED = {"role", "content", "name"}


def reply_for(system_and_user: str) -> dict:
    t = system_and_user
    if "Crop Monitoring" in t:
        return {"findings": [{"text": "Hot dry spell", "source_ids": ["W1", "X99"]}], "data_gaps": ["no EC"], "severity": "moderate"}
    if "Biological Diagnosis" in t:
        return {"hypotheses": [{"name": "Water stress", "likelihood": "moderate", "evidence_for": ["heat"], "evidence_against": [],
                                "source_ids": ["W1"]}], "primary_hypothesis": "Water stress", "evidence_confidence": "low",
                "additional_evidence_needed": ["EC"], "follow_up_questions": ["When irrigated?"]}
    if "Intervention Agent" in t:
        return {"options": [{"key": "A", "title": "Test", "quantities": {"soil_test_sample": 2, "labor_hour": 4}, "p_loss": 0.5},
                            {"key": "B", "title": "Irrigate", "quantities": {"pump_hour": 10}, "p_loss": 0.3, "delay_days": 2},
                            {"key": "C", "title": "Full", "quantities": {"labor_hour": 20}, "p_loss": 0.2}]}
    if "Risk & Compliance" in t:
        return {"per_option": [{"option_key": "A", "flags": [{"text": "check label", "status": "verified", "source_ids": []}]}], "overall_notes": []}
    if "Critic Agent" in t:
        return {"issues": [{"severity": "high", "text": "unconfirmed"}], "missing_data": ["EC"], "overconfident_claims": [],
                "confidence_adjustment": "lower", "note_to_reviewer": "test first"}
    if "Plain-Language Report Writer" in t:
        return {"headline": "h", "likely_cause_plain": "c", "options_plain": [{"key": "A", "title": "t", "one_line": "o"}],
                "next_steps": ["n"], "warnings": ["w"]}
    if "translator" in t.lower() or "translate" in t.lower():
        return {"english_text": "my leaves are yellow", "understood_local": "leaves yellow",
                "headline": "h", "likely_cause_plain": "c", "options_plain": [], "next_steps": [], "warnings": []}
    return {"notes": ["ok"]}


class Handler(BaseHTTPRequestHandler):
    log = []          # every request body received
    fail_reasoning = False

    def log_message(self, *a):  # silence
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        Handler.log.append(req)
        for i, m in enumerate(req.get("messages", [])):
            for k in m:
                if k not in ALLOWED:
                    return self._send(400, {"error": {"message": f"'messages.{i}' : for 'role:{m.get('role')}' the following must be "
                                                                 f"satisfied[('messages.{i}' : property '{k}' is unsupported)]",
                                                      "type": "invalid_request_error"}})
        if Handler.fail_reasoning and "reasoning_effort" in req:
            return self._send(400, {"error": {"message": "property 'reasoning_effort' is unsupported", "type": "invalid_request_error"}})
        text = " ".join(m["content"] if isinstance(m["content"], str) else " ".join(p.get("text", "") for p in m["content"])
                        for m in req["messages"])
        content = "<think>let me think {not json}</think>\n```json\n" + json.dumps(reply_for(text)) + "\n```"
        self._send(200, {"id": "x", "object": "chat.completion", "created": 0, "model": req.get("model", "m"),
                         "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})


def start():
    Handler.log = []
    Handler.fail_reasoning = False
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
