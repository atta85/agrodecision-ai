"""AgroDecision AI - human-in-the-loop multi-agent decision support for crop health."""
import os

# Keep CrewAI quiet and private: no telemetry calls from a public demo app.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

__version__ = "0.3.0"
