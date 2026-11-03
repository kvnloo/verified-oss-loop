"""Interrupt a running Hermes gateway turn by session id (native ``session.interrupt``).

Run with the Python that runs Hermes, e.g.
``~/.hermes/hermes-agent/.hermes/bin/python adapters/hermes/interrupt.py --profile P SESSION_ID``.
Killing a ``hermes chat`` client only detaches it -- the gateway keeps executing the accepted turn --
so cancellation must go through the gateway. Prints one JSON object; exit 0 only when the gateway
acknowledged the interrupt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


async def _interrupt(session_id: str) -> dict:
    from hermes_cli.gateway_client import connect_gateway  # Hermes' own client; no protocol re-implementation

    async with connect_gateway() as client:
        snap = await client.rpc("session.resume", session_id=session_id)
        sid = snap.get("stored_session_id", session_id)
        reply = await client.rpc("session.interrupt", session_id=sid,
                                 execution_generation=snap.get("execution_generation", 0))
        after = await client.rpc("session.resume", session_id=session_id)
        return {"session_id": sid, "interrupt": reply,
                "readback": {k: after.get(k) for k in ("running", "status", "execution_generation") if k in after}}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("session_id")
    a = p.parse_args()
    home = Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes"))
    os.environ["HERMES_HOME"] = str(home / "profiles" / a.profile) if a.profile != "default" else str(home)
    try:
        out = asyncio.run(_interrupt(a.session_id))
    except Exception as exc:  # report, never guess: an unacknowledged interrupt is not a cancel
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)[:500]}))
        return 1
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
