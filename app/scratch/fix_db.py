"""
🔧 fix_db.py — Dev Migration Script (MongoDB)
===============================================
File: app/scratch/fix_db.py

MongoDB is schema-less — no ALTER TABLE needed.
This script back-fills the `is_on_pip` field on all existing
absence_events documents that are missing it.

Run:
    python app/scratch/fix_db.py

Optional flags:
    --dry-run   → show what would change, don't write
    --verbose   → print every updated doc _id
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def fix_is_on_pip(dry_run: bool = False, verbose: bool = False) -> None:
    """
    Back-fill `is_on_pip: False` on absence_events docs that are missing the field.
    In MongoDB we don't ALTER TABLE — we just $set the missing field on existing docs.
    """
    from core.mongo_connect import ensure_mongo_ready, get_hr_db

    await ensure_mongo_ready()
    db  = get_hr_db()
    col = db.absences   # motor collection: absence_events

    # Count docs missing the field
    missing_count = await col.count_documents({"is_on_pip": {"$exists": False}})

    print(f"\n🔍 absence_events documents missing 'is_on_pip': {missing_count}")

    if missing_count == 0:
        print("✅ Nothing to fix — all documents already have 'is_on_pip'.")
        return

    if dry_run:
        print(f"🏃 DRY RUN — would back-fill {missing_count} documents with is_on_pip=False")
        if verbose:
            cursor = col.find({"is_on_pip": {"$exists": False}}, {"_id": 1})
            docs   = await cursor.to_list(None)
            for d in docs:
                print(f"   would update: {d['_id']}")
        return

    # Run the update
    result = await col.update_many(
        {"is_on_pip": {"$exists": False}},
        {"$set": {"is_on_pip": False}},
    )

    print(f"✅ Successfully back-filled 'is_on_pip=False' on {result.modified_count} documents.")

    if verbose:
        cursor = col.find({"is_on_pip": False}, {"_id": 1, "employee_id": 1, "absence_date": 1})
        docs   = await cursor.to_list(None)
        for d in docs:
            print(f"   updated: _id={d['_id']} | employee={d.get('employee_id')} | date={d.get('absence_date')}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MongoDB fix_db — back-fill is_on_pip")
    parser.add_argument("--dry-run",  action="store_true", help="Show changes without writing")
    parser.add_argument("--verbose",  action="store_true", help="Print every updated _id")
    args = parser.parse_args()

    print("🔧 fix_db.py — MongoDB back-fill migration")
    print("=" * 50)
    await fix_is_on_pip(dry_run=args.dry_run, verbose=args.verbose)
    print()


if __name__ == "__main__":
    asyncio.run(main())