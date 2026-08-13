#!/usr/bin/env python3
"""
One-time migration: move existing local unit images to Supabase Storage.

For every Unit with unit_images_json pointing at local `uploads/...` files,
this uploads the local file (from app/static/uploads/) to the Supabase bucket
and rewrites the stored path to the Supabase public URL — so images survive
Render redeploys.

Prerequisites (set in your .env before running):
    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET (public bucket)

Usage:
    .venv/bin/python migrate_images_to_supabase.py            # do the migration
    .venv/bin/python migrate_images_to_supabase.py --dry-run  # preview only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Unit
from app import supabase_storage

DRY_RUN = "--dry-run" in sys.argv


def resolve_local(path: str) -> Path | None:
    """Find the local file for a stored path like 'uploads/xyz.jpg'."""
    p = str(path).lstrip("/")
    candidates = [
        Path("app/static") / p,          # uploads/... -> app/static/uploads/...
        Path("app/static") / "uploads" / Path(p).name,
        Path(p),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def main() -> int:
    app = create_app()
    with app.app_context():
        if not supabase_storage.is_enabled():
            print("❌ Supabase Storage is not configured.")
            print("   Set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env first.")
            return 1

        bucket = app.config["SUPABASE_BUCKET"]
        print(f"🪣  Target bucket: {bucket}")
        print(f"{'🔎 DRY RUN — no changes will be saved' if DRY_RUN else '🚚 Migrating...'}")
        print("-" * 60)

        units = db.session.query(Unit).filter(Unit.unit_images_json.isnot(None)).all()
        moved = skipped = missing = 0

        for unit in units:
            try:
                paths = json.loads(unit.unit_images_json)
            except Exception:
                continue
            if not isinstance(paths, list):
                continue

            new_paths = []
            changed = False
            for path in paths:
                path = str(path)
                if path.startswith(("http://", "https://")):
                    new_paths.append(path)  # already migrated
                    skipped += 1
                    continue

                local = resolve_local(path)
                if not local:
                    print(f"  ⚠️  {unit.unit_code}: missing local file for '{path}'")
                    new_paths.append(path)
                    missing += 1
                    continue

                dest = f"units/{local.name}"
                if DRY_RUN:
                    print(f"  → {unit.unit_code}: {local} -> {bucket}/{dest}")
                    new_paths.append(supabase_storage.public_url(dest))
                    moved += 1
                    changed = True
                    continue

                data = local.read_bytes()
                url = supabase_storage.upload_bytes(data, dest)
                print(f"  ✅ {unit.unit_code}: {local.name} -> {url}")
                new_paths.append(url)
                moved += 1
                changed = True

            if changed and not DRY_RUN:
                unit.unit_images_json = json.dumps(new_paths)

        if not DRY_RUN:
            db.session.commit()

        print("-" * 60)
        print(f"Done. uploaded={moved}  already-migrated={skipped}  missing={missing}")
        if DRY_RUN:
            print("Re-run without --dry-run to apply.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
