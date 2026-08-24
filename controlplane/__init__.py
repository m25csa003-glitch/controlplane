"""ControlPlane - a verification layer between an application and any LLM API."""

# Keys come from the environment, never from code or config. .env is a local
# convenience that populates the environment and is gitignored; nothing reads a
# key from anywhere else.
try:
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass
