"""
Safely read and update .env file values.

Uses python-dotenv's set_key() to modify individual keys
without disturbing comments or other values.
"""

from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def get_env_value(key: str) -> str | None:
    """Read a value from .env without loading into os.environ."""
    values = dotenv_values(ENV_PATH)
    return values.get(key)


def update_env_value(key: str, value: str):
    """Update or insert a key in .env file, preserving formatting."""
    if not ENV_PATH.exists():
        example = PROJECT_ROOT / ".env.example"
        if example.exists():
            ENV_PATH.write_text(example.read_text())
        else:
            ENV_PATH.touch()

    success, key_out, value_out = set_key(str(ENV_PATH), key, value)
    if success:
        print(f"  .env updated: {key}={value[:20]}{'...' if len(value) > 20 else ''}")
    else:
        print(f"  WARNING: Failed to update {key} in .env")

    load_dotenv(ENV_PATH, override=True)
