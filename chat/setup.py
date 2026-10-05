"""Create private settings; optionally change the password interactively."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat.paths import private_dir, settings_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-password", action="store_true", help="Prompt for a new password without putting it in shell history")
    parser.add_argument("--upstream", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen3.8-27b")
    parser.add_argument("--model-label", default="Qwen3.8 · 27B")
    args = parser.parse_args()
    folder = private_dir()
    folder.mkdir(parents=True, exist_ok=True)
    config_path = settings_path()
    if config_path.exists() and not args.set_password:
        print("Existing settings preserved:", config_path)
        return
    if args.set_password:
        password = getpass.getpass("New access password (at least 12 characters): ")
        if len(password) < 12 or password != getpass.getpass("Confirm password: "):
            raise SystemExit("Password too short or confirmation did not match; settings were not changed")
    else:
        password = secrets.token_urlsafe(18)
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {
        "upstream": args.upstream, "model": args.model, "model_label": args.model_label,
    }
    salt = secrets.token_bytes(16)
    config.update(password_salt=salt.hex(), password_hash=hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex(), session_secret=secrets.token_hex(32))
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Restrict the directory before writing plaintext credentials.
    if os.name == "nt":
        sid = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True).stdout.strip().split(',')[-1].strip('"')
        subprocess.run(["icacls", str(folder), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], check=True, stdout=subprocess.DEVNULL)
    else:
        folder.chmod(0o700)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    access = folder / "access.txt"
    access.write_text("Photo Coach access password\n\n" + password + "\n", encoding="utf-8")
    if os.name != "nt":
        config_path.chmod(0o600)
        access.chmod(0o600)
    print("Private settings ready:", config_path)
    print("Read your generated password locally in:", access)


if __name__ == "__main__":
    main()
