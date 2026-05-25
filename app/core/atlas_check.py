"""
Atlas connectivity check — run: python -m core.atlas_check

Shows your public IP (add it in Atlas Network Access) and tests MongoDB ping.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()

ATLAS_NETWORK_URL = (
    "https://cloud.mongodb.com/v2/6a0f8245d16844e9d18ebf91"
    "#/security/network/accessList"
)
ATLAS_EXPLORER_URL = (
    "https://cloud.mongodb.com/v2/6a0f8245d16844e9d18ebf91"
    "#/explorer/6a0f82e424f02538128d6997/ERP/finance_audit/find"
)


def _public_ip() -> str:
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
    except Exception:
        return "unknown"


def _dns_ok(host: str = "erp.dffbywk.mongodb.net") -> bool:
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


async def _ping_atlas() -> None:
    from core.mongo_client import create_mongo_client, resolve_mongo_uri, verify_mongo_connection
    import os

    uri = resolve_mongo_uri()
    db_name = os.getenv("MONGO_DB", "ERP").strip()
    print(f"URI host: {uri.split('@')[-1].split('/')[0]}")
    print(f"Database: {db_name}")
    print("Connecting...")

    client = create_mongo_client(uri)
    try:
        info = await verify_mongo_connection(client, db_name)
        n = await client[db_name]["finance_audit"].estimated_document_count()
        print(f"[OK] Atlas connected | MongoDB {info.get('version')} | finance_audit docs={n}")
        print(f"Explorer: {ATLAS_EXPLORER_URL}")
    finally:
        client.close()


def main() -> None:
    print("\n=== MongoDB Atlas check ===\n")
    print(f"Your public IP (add in Atlas Network Access): {_public_ip()}")
    print(f"Network Access page:\n  {ATLAS_NETWORK_URL}\n")
    print("Steps:")
    print("  1. Atlas -> Network Access -> ADD IP ADDRESS")
    print("  2. Choose 'Add Your Current IP Address' OR 'Allow Access from Anywhere' (0.0.0.0/0)")
    print("  3. Wait 1-2 minutes, then run: python -m core.mongo_connect\n")

    if not _dns_ok():
        print("[WARN] DNS lookup for erp.dffbywk.mongodb.net failed — check internet/DNS\n")

    try:
        asyncio.run(_ping_atlas())
    except Exception as e:
        err = str(e)
        print(f"\n[FAIL] {err[:500]}\n")
        if "TLSV1_ALERT_INTERNAL_ERROR" in err or "SSL handshake" in err:
            print("This error is almost always Atlas Network Access (IP not allowed).")
            print("Browser Explorer works; Python needs IP in the access list.")
        sys.exit(1)


if __name__ == "__main__":
    main()
