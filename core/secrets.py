"""Read secrets from `<NAME>_FILE` paths (Docker) or plain env vars (CI).

The keygen container writes each secret to a 0400 file. CI passes dummy
values directly as env vars. A `_FILE` path always wins over the plain var.
"""

import os
from pathlib import Path


def read_secret(name: str, default: str | None = None) -> str | None:
    path = os.environ.get(f"{name}_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]
