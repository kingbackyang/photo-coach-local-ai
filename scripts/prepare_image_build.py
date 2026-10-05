"""Fetch pinned official GGUF plugin source and its small dependency wheel."""
import argparse
import hashlib
from pathlib import Path

import httpx

COMMIT = "e2b8ad532b8b5ea175100202c30430c1d2b5e6a8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy", help="Optional HTTP proxy for GitHub/PyPI only; model downloads always bypass proxies")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "docker/vllm-gguf/vendor"
    destination.mkdir(parents=True, exist_ok=True)
    with httpx.Client(proxy=args.proxy, follow_redirects=True, timeout=120) as client:
        source = client.get(f"https://codeload.github.com/vllm-project/vllm-gguf-plugin/tar.gz/{COMMIT}")
        source.raise_for_status()
        (destination / "plugin.tar.gz").write_bytes(source.content)
        metadata = client.get("https://pypi.org/pypi/gguf/0.19.0/json")
        metadata.raise_for_status()
        package = next(row for row in metadata.json()["urls"] if row["filename"] == "gguf-0.19.0-py3-none-any.whl")
        wheel = client.get(package["url"])
        wheel.raise_for_status()
        assert hashlib.sha256(wheel.content).hexdigest() == package["digests"]["sha256"]
        (destination / package["filename"]).write_bytes(wheel.content)
    print("Source pinned:", COMMIT)
    print("Official gguf dependency wheel SHA256 verified; build context:", destination.parent)


if __name__ == "__main__":
    main()
