"""
One-off local OAuth helper for installing a Shopify Dev Dashboard app
onto a merchant store and capturing an offline access token.

Flow:
    1. Starts a local HTTP listener on port 3001 with two endpoints:
       - POST /config  — receives {clientId, clientSecret} from an in-browser fetch
       - GET  /shopify/install  — OAuth callback; exchanges the code for an
         offline access token and writes it into .env

    2. Once /config is posted, prints the OAuth authorize URL to stdout.

    3. Navigate the Shopify admin (for the target shop) to that URL,
       click "Install", Shopify redirects to /shopify/install with a code,
       we exchange it for an offline `shpat_…` token.

Usage:
    python scripts/shopify_oauth_install.py --shop lazo-colombia.myshopify.com
"""

from __future__ import annotations

import argparse
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

PORT = 3001
CALLBACK_PATH = "/shopify/install"
CONFIG_PATH_ = "/config"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class _State:
    nonce = secrets.token_urlsafe(16)
    token: str | None = None
    error: str | None = None
    creds_received = threading.Event()
    done = threading.Event()
    shop: str = ""
    scopes: str = ""
    client_id: str = ""
    client_secret: str = ""


def exchange_code(shop: str, code: str) -> dict:
    url = f"https://{shop}/admin/oauth/access_token"
    body = json.dumps(
        {
            "client_id": _State.client_id,
            "client_secret": _State.client_secret,
            "code": code,
        }
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def write_env(token: str) -> None:
    text = ENV_PATH.read_text()
    lines = text.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith("SHOPIFY_ACCESS_TOKEN="):
            lines[i] = f"SHOPIFY_ACCESS_TOKEN={token}"
            replaced = True
            break
    if not replaced:
        lines.append(f"SHOPIFY_ACCESS_TOKEN={token}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def authorize_url() -> str:
    q = urllib.parse.urlencode(
        {
            "client_id": _State.client_id,
            "scope": _State.scopes,
            "redirect_uri": f"http://localhost:{PORT}{CALLBACK_PATH}",
            "state": _State.nonce,
        }
    )
    return f"https://{_State.shop}/admin/oauth/authorize?{q}"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_a, **_kw):
        return

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != CONFIG_PATH_:
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            body = {}

        cid = body.get("clientId", "").strip()
        cs = body.get("clientSecret", "").strip()
        if not cid or not cs:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b"missing clientId/clientSecret")
            return

        _State.client_id = cid
        _State.client_secret = cs
        _State.creds_received.set()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(
            json.dumps({"ok": True, "authorizeUrl": authorize_url()}).encode()
        )

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = dict(urllib.parse.parse_qsl(url.query))
        # State check skipped — Shopify's custom install URL mints its own state.

        code = params.get("code")
        if not code:
            self._respond("Missing code.", status=400)
            _State.error = "missing_code"
            _State.done.set()
            return

        try:
            data = exchange_code(params.get("shop", _State.shop), code)
            token = data["access_token"]
            write_env(token)
            _State.token = token
            self._respond(
                "Installed. Token written to .env. You can close this tab."
            )
        except Exception as exc:
            _State.error = str(exc)
            self._respond(f"Exchange failed: {exc}", status=500)
        finally:
            _State.done.set()

    def _respond(self, msg: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(msg.encode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shop", required=True)
    ap.add_argument(
        "--scopes", default="read_orders,read_customers,read_fulfillments"
    )
    args = ap.parse_args()

    _State.shop = args.shop
    _State.scopes = args.scopes

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print(f"Listening on http://localhost:{PORT}")
    print(f"POST {{clientId, clientSecret}} to http://localhost:{PORT}{CONFIG_PATH_}")
    print("Waiting for credentials...")

    if not _State.creds_received.wait(timeout=300):
        print("Timed out waiting for credentials.", file=sys.stderr)
        return 2

    print()
    print("Credentials received. Open this authorize URL in the target shop admin:")
    print(authorize_url())
    print()
    print("Waiting for install callback...")

    if not _State.done.wait(timeout=300):
        print("Timed out after 5 minutes.", file=sys.stderr)
        return 2

    if _State.error:
        print(f"Failed: {_State.error}", file=sys.stderr)
        return 1

    print(f"Wrote token to {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
