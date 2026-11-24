"""Start an isolated, read-only public demo; never read the owner's .env file."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def normalized_public_url(value: str) -> str:
    """Accept one explicit HTTPS origin, without credentials or URL paths."""
    value = value.strip()
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise ValueError("PUBLIC_URL must be a valid HTTPS origin.") from exc
    if (
        parsed.scheme != "https"
        or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host)
        or ".." in host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.netloc.endswith(":")
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("PUBLIC_URL must be an HTTPS origin without credentials, path, query, or fragment.")
    authority = host.lower() + (f":{port}" if port not in (None, 443) else "")
    return urlunsplit(("https", authority, "", "", ""))


def deployment_config(environ=None) -> dict:
    env = os.environ if environ is None else environ
    public_url = env.get("PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or env.get("DEMO_PUBLIC_URL", "")
    if not public_url:
        raise ValueError("Set PUBLIC_URL or RENDER_EXTERNAL_URL to the demo's exact HTTPS URL before starting.")
    public_url = normalized_public_url(public_url)
    try:
        port = int(env.get("PORT", "10000"))
    except ValueError as exc:
        raise ValueError("PORT must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535.")
    # A local DATA_DIR environment variable might point at personal research.
    # Only the separate DEMO_DATA_DIR setting may select demo storage.
    data_dir = Path(env.get("DEMO_DATA_DIR") or Path(tempfile.gettempdir()) / "research-assistant-demo").expanduser().resolve()
    if data_dir == ROOT or data_dir in ROOT.parents or data_dir.is_relative_to(ROOT / "data"):
        raise ValueError("DEMO_DATA_DIR must be separate from the project root and personal data/ directory.")
    bind_host = env.get("DEMO_BIND_HOST", "0.0.0.0")
    if bind_host not in {"0.0.0.0", "127.0.0.1", "::1"}:
        raise ValueError("DEMO_BIND_HOST must be 0.0.0.0, 127.0.0.1, or ::1.")
    return {"public_url": public_url, "data_dir": str(data_dir), "port": port, "bind_host": bind_host}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate deployment configuration without starting the app.")
    args = parser.parse_args()
    try:
        config = deployment_config()
    except ValueError as exc:
        parser.exit(2, f"Demo configuration error: {exc}\n")

    if args.check:
        print(json.dumps({"deployment_mode": "demo", **config}, ensure_ascii=False))
        return 0

    # Set these before importing app.main, which also exposes its default ASGI app.
    os.environ.update({
        "DEPLOYMENT_MODE": "demo",
        "DEMO_PUBLIC_URL": config["public_url"],
        "DATA_DIR": config["data_dir"],
        "AI_BASE_URL": "",
        "AI_API_KEY": "",
        "AI_CHAT_MODEL": "",
        "EMBEDDING_BASE_URL": "",
        "EMBEDDING_API_KEY": "",
        "EMBEDDING_MODEL": "",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    })
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import Settings
    from app.main import create_app
    import uvicorn

    settings = Settings(
        _env_file=None,
        deployment_mode="demo",
        demo_public_url=config["public_url"],
        data_dir=config["data_dir"],
        ai_base_url="", ai_api_key="", ai_chat_model="",
        embedding_base_url="", embedding_api_key="", embedding_model="",
    )
    # BackgroundTasks + SQLite are intentionally confined to one application worker.
    uvicorn.run(create_app(settings=settings), host=config["bind_host"], port=config["port"], workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
