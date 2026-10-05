"""Render private server/client configuration for your own IPv4 cloud server."""
import argparse
import ipaddress
from pathlib import Path
import secrets
import sys

import certifi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat.paths import private_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--public-port", type=int, default=3389)
    args = parser.parse_args()
    address = ipaddress.IPv4Address(args.server_ip)
    if not address.is_global:
        parser.error("Use your real globally routable server IPv4 address")
    if not 1024 <= args.public_port <= 65535 or args.public_port in {7000, 18080}:
        parser.error("Public port must be 1024..65535 and different from internal relay ports")
    private = private_dir()
    if not (private / "settings.json").exists():
        raise SystemExit("Run chat/setup.py first to initialize the protected private directory")
    token_path = private / "relay-token.txt"
    if not token_path.exists():
        token_path.write_text(secrets.token_hex(32), encoding="utf-8")
    token = token_path.read_text(encoding="utf-8").strip()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise SystemExit("Unexpected relay token format; existing files were not overwritten")
    root = Path(__file__).resolve().parents[1]
    nginx = (root / "deploy/nginx.conf.template").read_text(encoding="utf-8").replace("__IP__", str(address)).replace("__PUBLIC_PORT__", str(args.public_port))
    server = (root / "deploy/server-setup.sh.template").read_text(encoding="utf-8").replace("__IP__", str(address)).replace("__RELAY_TOKEN__", token).replace("__NGINX_CONFIG__", nginx.rstrip())
    (private / "deploy-server.sh").write_text(server, encoding="utf-8", newline="\n")
    client = f'''serverAddr = "{address}"
serverPort = 443
loginFailExit = false
transport.protocol = "wss"
transport.tls.enable = true
transport.tls.serverName = "{address}"
transport.tls.trustedCaFile = '{certifi.where()}'
auth.method = "token"
auth.tokenSource.type = "file"
auth.tokenSource.file.path = '{token_path}'
log.to = '{private / "relay.log"}'
log.level = "warn"
log.maxDays = 7
[[proxies]]
name = "inference-chat"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8088
remotePort = 18080
'''
    (private / "frpc.toml").write_text(client, encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        for name in ["relay-token.txt", "deploy-server.sh", "frpc.toml"]:
            (private / name).chmod(0o600)
    print("Private deployment script:", private / "deploy-server.sh")
    print("Private relay client config:", private / "frpc.toml")
    print(f"Website after deployment: https://{address}:{args.public_port}/")
    print("Upload only the private server script and official Linux FRP archive to your server; do not commit them")


if __name__ == "__main__":
    main()
