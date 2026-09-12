#!/usr/bin/env python3
"""Decide if a claim lease is expired. JSON comments array on stdin.

Used by expire-claims.sh. Stdlib only. Does not call gh. Does not merge.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

ISO = re.compile(
    r"(?:expires_at|expires)\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})?)",
    re.I,
)


def main() -> int:
    now = int(os.environ["VOL_NOW_EPOCH"])
    max_age = int(os.environ["VOL_MAX_AGE_SECS"])
    comments = json.load(sys.stdin)
    claim_at = None
    expiry = None
    for c in comments:
        body = c.get("body") or ""
        created = c.get("createdAt") or c.get("created_at") or ""
        if re.search(r"(?i)claiming for|claimant:|claimed_at:", body):
            try:
                claim_at = int(datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass
        for m in ISO.finditer(body):
            raw = m.group(1)
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                expiry = int(datetime.datetime.fromisoformat(raw).timestamp())
            except Exception:
                pass
    if expiry is not None:
        expired = expiry <= now
        reason = f"expires_at {expiry} <= now {now}"
    elif claim_at is not None:
        expired = (now - claim_at) >= max_age
        reason = f"claim comment age {now - claim_at}s >= {max_age}s"
    else:
        expired = False
        reason = "no claim timestamp"
    print("yes" if expired else "no")
    print(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
