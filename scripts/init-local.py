"""Create missing local bootstrap credentials without replacing existing settings."""

import os
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "platform/.env"
existing = path.read_text() if path.exists() else ""
keys = {line.split("=", 1)[0].strip() for line in existing.splitlines() if "=" in line and not line.lstrip().startswith("#")}
defaults = {
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": secrets.token_urlsafe(32),
    "SECRET_KEY": secrets.token_urlsafe(48),
}
missing = [f"{key}={value}\n" for key, value in defaults.items() if key not in keys]
if missing:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a") as stream:
        if existing and not existing.endswith("\n"):
            stream.write("\n")
        stream.writelines(missing)
    print(f"Added missing local settings to {path}. Existing values preserved.")
else:
    print("Local settings already present; unchanged.")
