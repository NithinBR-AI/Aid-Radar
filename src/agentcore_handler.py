"""
AgentCore Runtime entry point.

Wraps the AidRadar pipeline as an HTTP server on port 8080.
AgentCore sends POST /invoke with a JSON body; we run the pipeline and return the result.
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from src.pipeline.runner import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/invoke":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            intake_profile = json.loads(body)
        except json.JSONDecodeError as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        result = run_pipeline(intake_profile)
        response = {
            "success": result.success,
            "report": result.report_text,
            "eligibility": result.eligibility_text,
            "programs": result.programs,
            "profile_id": result.profile_id,
            "error": result.error,
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info("AidRadar AgentCore handler starting on port %d", port)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
