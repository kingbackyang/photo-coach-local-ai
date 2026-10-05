"""Download verified official FRP 0.71.0 archives; optionally extract the Windows client."""
import argparse
import hashlib
from pathlib import Path
import zipfile

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path(r"C:\AIInference\runtime\frp"))
    parser.add_argument("--proxy")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    with httpx.Client(proxy=args.proxy, follow_redirects=True, timeout=180) as client:
        release = client.get("https://api.github.com/repos/fatedier/frp/releases/tags/v0.71.0")
        release.raise_for_status()
        rows = release.json()["assets"]
        for filename in ["frp_0.71.0_windows_amd64.zip", "frp_0.71.0_linux_amd64.tar.gz"]:
            asset = next(row for row in rows if row["name"] == filename)
            digest = asset.get("digest", "")
            if not digest.startswith("sha256:"):
                raise RuntimeError("Official release did not provide a SHA256 digest")
            target = args.destination / filename
            if not target.exists():
                response = client.get(asset["browser_download_url"])
                response.raise_for_status()
                target.write_bytes(response.content)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == digest.removeprefix("sha256:"), filename
            if filename.endswith(".zip"):
                with zipfile.ZipFile(target) as archive:
                    for entry in archive.infolist():
                        if not (args.destination / entry.filename).resolve().is_relative_to(args.destination.resolve()):
                            raise RuntimeError("Unexpected archive path")
                    archive.extractall(args.destination)
            print("SHA256 verified:", target)


if __name__ == "__main__":
    main()
