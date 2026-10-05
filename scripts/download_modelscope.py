"""Download pinned ModelScope files directly, with resume and SHA256 validation."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time

import requests


def download(entry, root, logs, verify_only=False):
    destination = root / entry["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    log_path = logs / (entry["destination"].replace("/", "_") + ".json")
    state = {**entry, "state": "downloading", "proxy": False}

    def save():
        log_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def verify(path):
        if path.stat().st_size != entry["size"]:
            raise RuntimeError(f"Wrong file size: {path}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != entry["sha256"]:
            raise RuntimeError(f"SHA256 mismatch: {path}")

    if not destination.exists():
        if verify_only:
            raise FileNotFoundError(destination)
        session = requests.Session()
        session.trust_env = False  # Also ignores Windows system proxy settings.
        with session:
            for attempt in range(8):
                offset = partial.stat().st_size if partial.exists() else 0
                if offset == entry["size"]:
                    break
                if offset > entry["size"]:
                    raise RuntimeError(f"Partial file is too large: {partial}")
                try:
                    with session.get(f"https://modelscope.cn/api/v1/models/{entry['repo']}/repo", params={"Revision": entry["revision"], "FilePath": entry["file"]}, headers={"Range": f"bytes={offset}-"} if offset else {}, stream=True, timeout=(15, 45)) as response:
                        response.raise_for_status()
                        if offset and (response.status_code != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                            raise RuntimeError("Server did not honor Range; the partial file was preserved")
                        last_report = time.monotonic()
                        with partial.open("ab" if offset else "wb") as stream:
                            for chunk in response.iter_content(1024 * 1024):
                                if not chunk:
                                    continue
                                stream.write(chunk)
                                offset += len(chunk)
                                if offset > entry["size"]:
                                    raise RuntimeError("Download exceeds the pinned size")
                                if time.monotonic() - last_report >= 3:
                                    state["downloadedBytes"] = offset
                                    save()
                                    print(f"{entry['file']}: {offset / entry['size']:.1%}", flush=True)
                                    last_report = time.monotonic()
                    if offset != entry["size"]:
                        raise RuntimeError("Download ended early")
                    break
                except (requests.RequestException, RuntimeError) as error:
                    state.update(error=str(error), attempt=attempt + 1)
                    save()
                    if attempt == 7:
                        raise
                    time.sleep(min(2 * (attempt + 1), 10))
        verify(partial)
        partial.replace(destination)
    else:
        verify(destination)
    state.update(state="verified", downloadedBytes=entry["size"])
    save()
    print("VERIFIED", entry["destination"], flush=True)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(r"C:\AIModels"))
    parser.add_argument("--logs", type=Path, default=Path("benchmark-results/downloads"))
    parser.add_argument("--group", choices=["chat", "image", "all"], default="chat")
    parser.add_argument("--include", help="Download only this manifest filename (useful for a small config smoke test)")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "models.lock.json").read_text(encoding="utf-8"))
    entries = [entry for entry in manifest["files"] if (args.group == "all" or entry["group"] == args.group) and (not args.include or entry["file"] == args.include)]
    if not entries:
        raise SystemExit("No matching files")
    for entry in entries:
        print(f"{entry['destination']}  {entry['size'] / 1e9:.3f} GB")
    print(f"Total: {sum(entry['size'] for entry in entries) / 1e9:.3f} GB; ModelScope direct connection")
    if args.dry_run:
        return
    args.logs.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(download, entry, args.root, args.logs, args.verify_only) for entry in entries]
        results = [future.result() for future in futures]
    (args.logs / "verified.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
