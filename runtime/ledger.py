"""Single-writer attempt ledger for the Verified OSS Loop factory runtime. Stdlib only.

This is the narrow seam the factory needs and native harnesses do not supply:

* atomic lease acquire with a monotonic fence per (task, role) scope;
* renewal by owner+fence compare-and-set; expiry by wall clock;
* a durable submit intent written BEFORE any harness call;
* reconcile-on-unknown: an intent whose outcome is unknown is reconciled from native
  evidence and is never re-sent;
* stale-fence rejection and idempotent completion;
* held dispositions that block a lane with a reason and resume trigger.

It is not a scheduler, router, quota daemon or accounting ledger. One process opens the
database at a time per write (SQLite ``BEGIN IMMEDIATE``); readers may run concurrently.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ROLES = ("builder", "verifier")
STATES = ("authorized", "submitted", "reconciling", "completed", "independently_verified", "held")
UNRESOLVED = ("authorized", "submitted", "reconciling")
SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  repo TEXT NOT NULL,
  issue TEXT NOT NULL,
  base_revision TEXT NOT NULL,
  goal_lock TEXT NOT NULL,
  goal_digest TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS leases (
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,
  owner TEXT,
  fence INTEGER NOT NULL,
  expires_at REAL NOT NULL,
  PRIMARY KEY (task_id, role)
);
CREATE TABLE IF NOT EXISTS holds (
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,
  reason TEXT NOT NULL,
  resume_trigger TEXT NOT NULL,
  at REAL NOT NULL,
  PRIMARY KEY (task_id, role)
);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,
  fence INTEGER NOT NULL,
  lease_owner TEXT NOT NULL,
  submit_intent_id TEXT NOT NULL UNIQUE,
  native TEXT NOT NULL,
  session_id TEXT,
  head_revision TEXT,
  verifies_attempt TEXT,
  state TEXT NOT NULL,
  reason TEXT,
  resume_trigger TEXT,
  revoked INTEGER NOT NULL DEFAULT 0,
  evidence TEXT NOT NULL DEFAULT '{}',
  result_digest TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  UNIQUE (task_id, role, fence)
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id TEXT,
  task_id TEXT,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  at REAL NOT NULL
);
"""


class LedgerError(Exception):
    """Base class; ``code`` is a stable machine-readable reason."""

    code = "ledger_error"


class LeaseHeld(LedgerError):
    code = "lease_held"


class StaleFence(LedgerError):
    code = "stale_fence"


class AlreadySubmitted(LedgerError):
    code = "already_submitted"


class NeedsReconcile(LedgerError):
    code = "needs_reconcile"


class LaneHeld(LedgerError):
    code = "lane_held"


class GoalLockMismatch(LedgerError):
    code = "goal_lock_mismatch"


class InvalidEvidence(LedgerError):
    code = "invalid_evidence"


class SelfReview(LedgerError):
    code = "self_review"


class CompletionConflict(LedgerError):
    code = "completion_conflict"


@dataclass(frozen=True)
class Lease:
    task_id: str
    role: str
    owner: str
    fence: int
    expires_at: float


def digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Ledger:
    def __init__(self, path: str | Path, clock: Callable[[], float] = time.time):
        self.path = str(path)
        self.clock = clock
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        db = self._connect()
        try:
            db.executescript(_DDL)
            db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        finally:
            db.close()

    # -- plumbing -------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    class _Tx:
        def __init__(self, ledger: "Ledger"):
            self.ledger = ledger

        def __enter__(self) -> sqlite3.Connection:
            self.db = self.ledger._connect()
            self.db.execute("BEGIN IMMEDIATE")
            return self.db

        def __exit__(self, exc_type, exc, tb):
            try:
                self.db.execute("ROLLBACK" if exc_type else "COMMIT")
            finally:
                self.db.close()
            return False

    def _tx(self) -> "Ledger._Tx":
        return Ledger._Tx(self)

    def _event(self, db, kind: str, payload: dict, attempt_id: str | None = None, task_id: str | None = None):
        db.execute("INSERT INTO events(attempt_id, task_id, kind, payload, at) VALUES (?,?,?,?,?)",
                   (attempt_id, task_id, kind, json.dumps(payload, sort_keys=True), self.clock()))

    # -- tasks ----------------------------------------------------------------------------

    def register_task(self, task: dict) -> str:
        """Freeze task identity and goal lock. Re-registering the same lock is a no-op; a different
        lock for the same task id is refused (goal drift is a new task, not a silent edit)."""
        base = str(task["base_revision"]).lower()
        if not FULL_SHA.match(base):
            raise InvalidEvidence("base_revision must be a full 40-character SHA")
        lock = task["goal_lock"]
        gd = digest(lock)
        with self._tx() as db:
            row = db.execute("SELECT goal_digest, base_revision FROM tasks WHERE task_id=?", (task["task_id"],)).fetchone()
            if row:
                if row["goal_digest"] != gd or row["base_revision"] != base:
                    raise GoalLockMismatch(f"task {task['task_id']} is already registered with another goal lock")
                return task["task_id"]
            db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                       (task["task_id"], task["repo"], str(task["issue"]), base, json.dumps(lock, sort_keys=True), gd, self.clock()))
            self._event(db, "task_registered", {"goal_digest": gd, "base_revision": base}, task_id=task["task_id"])
        return task["task_id"]

    def task(self, task_id: str) -> dict:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise LedgerError(f"unknown task {task_id}")
        out = dict(row)
        out["goal_lock"] = json.loads(out["goal_lock"])
        return out

    # -- leases ---------------------------------------------------------------------------

    def acquire(self, task_id: str, role: str, owner: str, ttl: float) -> Lease:
        """Atomically take the (task, role) lease. Returns a strictly larger fence on each new grant."""
        if role not in ROLES:
            raise LedgerError(f"unknown role {role}")
        now = self.clock()
        with self._tx() as db:
            if not db.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone():
                raise LedgerError(f"unknown task {task_id}")
            row = db.execute("SELECT owner, fence, expires_at FROM leases WHERE task_id=? AND role=?",
                             (task_id, role)).fetchone()
            if row and row["owner"] == owner and row["expires_at"] > now:
                return Lease(task_id, role, owner, row["fence"], row["expires_at"])
            # GUARD:claim-race -- a live lease held by another owner is never shared.
            if row and row["owner"] and row["expires_at"] > now:
                raise LeaseHeld(f"{task_id}/{role} is leased to {row['owner']} (fence {row['fence']})")
            # Expiry alone is not proof the old worker stopped: an unresolved attempt under an older
            # fence must be reconciled or revoked (with readback) before a replacement is granted.
            stale = db.execute(
                f"SELECT attempt_id, state FROM attempts WHERE task_id=? AND role=? AND revoked=0 "
                f"AND state IN ({','.join('?' * len(UNRESOLVED))})", (task_id, role, *UNRESOLVED)).fetchone()
            if stale:
                raise NeedsReconcile(f"attempt {stale['attempt_id']} is {stale['state']}; reconcile or revoke first")
            fence = (row["fence"] if row else 0) + 1
            expires = now + ttl
            db.execute("INSERT INTO leases(task_id, role, owner, fence, expires_at) VALUES (?,?,?,?,?) "
                       "ON CONFLICT(task_id, role) DO UPDATE SET owner=excluded.owner, fence=excluded.fence, "
                       "expires_at=excluded.expires_at", (task_id, role, owner, fence, expires))
            self._event(db, "lease_acquired", {"role": role, "owner": owner, "fence": fence, "expires_at": _iso(expires)},
                        task_id=task_id)
        return Lease(task_id, role, owner, fence, expires)

    def renew(self, lease: Lease, ttl: float) -> Lease:
        now = self.clock()
        expires = now + ttl
        with self._tx() as db:
            cur = db.execute("UPDATE leases SET expires_at=? WHERE task_id=? AND role=? AND owner=? AND fence=? "
                             "AND expires_at>?", (expires, lease.task_id, lease.role, lease.owner, lease.fence, now))
            if cur.rowcount != 1:
                raise StaleFence(f"renew refused for {lease.task_id}/{lease.role} fence {lease.fence}")
            self._event(db, "lease_renewed", {"fence": lease.fence, "expires_at": _iso(expires)}, task_id=lease.task_id)
        return Lease(lease.task_id, lease.role, lease.owner, lease.fence, expires)

    def release(self, lease: Lease) -> None:
        with self._tx() as db:
            db.execute("UPDATE leases SET owner=NULL, expires_at=0 WHERE task_id=? AND role=? AND owner=? AND fence=?",
                       (lease.task_id, lease.role, lease.owner, lease.fence))
            self._event(db, "lease_released", {"fence": lease.fence}, task_id=lease.task_id)

    def _check_fence(self, db, lease: Lease) -> None:
        row = db.execute("SELECT owner, fence, expires_at FROM leases WHERE task_id=? AND role=?",
                         (lease.task_id, lease.role)).fetchone()
        # GUARD:stale-fence -- only the current, unexpired owner+fence may write.
        if not row or row["owner"] != lease.owner or row["fence"] != lease.fence or row["expires_at"] <= self.clock():
            raise StaleFence(f"fence {lease.fence} for {lease.task_id}/{lease.role} is not current")

    # -- holds ----------------------------------------------------------------------------

    def hold(self, task_id: str, role: str, reason: str, resume_trigger: str, attempt_id: str | None = None) -> None:
        if not reason or not resume_trigger:
            raise LedgerError("a hold needs a reason and a resume trigger")
        with self._tx() as db:
            db.execute("INSERT INTO holds VALUES (?,?,?,?,?) ON CONFLICT(task_id, role) DO UPDATE SET "
                       "reason=excluded.reason, resume_trigger=excluded.resume_trigger, at=excluded.at",
                       (task_id, role, reason, resume_trigger, self.clock()))
            if attempt_id:
                db.execute("UPDATE attempts SET state='held', reason=?, resume_trigger=?, updated_at=? WHERE attempt_id=?",
                           (reason, resume_trigger, self.clock(), attempt_id))
            self._event(db, "held", {"role": role, "reason": reason, "resume_trigger": resume_trigger},
                        attempt_id=attempt_id, task_id=task_id)

    def lift_hold(self, task_id: str, role: str, observed_trigger: str) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM holds WHERE task_id=? AND role=?", (task_id, role))
            self._event(db, "hold_lifted", {"role": role, "observed_trigger": observed_trigger}, task_id=task_id)

    def held(self, task_id: str, role: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT reason, resume_trigger FROM holds WHERE task_id=? AND role=?", (task_id, role)).fetchone()
        return dict(row) if row else None

    # -- submit outbox --------------------------------------------------------------------

    def begin_submit(self, lease: Lease, native: dict, verifies_attempt: str | None = None) -> tuple[str, str]:
        """Durably record the submit intent before any harness call. One intent per fence."""
        now = self.clock()
        with self._tx() as db:
            self._check_fence(db, lease)
            hold = db.execute("SELECT reason, resume_trigger FROM holds WHERE task_id=? AND role=?",
                              (lease.task_id, lease.role)).fetchone()
            if hold:
                raise LaneHeld(f"{lease.task_id}/{lease.role} held: {hold['reason']} (resume: {hold['resume_trigger']})")
            # GUARD:no-resend -- an existing intent under this fence means the call may already have happened.
            prior = db.execute("SELECT attempt_id, state FROM attempts WHERE task_id=? AND role=? AND fence=?",
                               (lease.task_id, lease.role, lease.fence)).fetchone()
            if prior:
                raise AlreadySubmitted(f"fence {lease.fence} already has attempt {prior['attempt_id']} ({prior['state']})")
            attempt_id = "att-" + uuid.uuid4().hex[:16]
            intent = "intent-" + uuid.uuid4().hex
            db.execute("INSERT INTO attempts(attempt_id, task_id, role, fence, lease_owner, submit_intent_id, native, "
                       "verifies_attempt, state, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, 'authorized', ?, ?)",
                       (attempt_id, lease.task_id, lease.role, lease.fence, lease.owner, intent,
                        json.dumps(native, sort_keys=True), verifies_attempt, now, now))
            self._event(db, "submit_intent", {"intent": intent, "fence": lease.fence, "native": native},
                        attempt_id=attempt_id, task_id=lease.task_id)
        return attempt_id, intent

    def bind_native(self, attempt_id: str, session_id: str, extra: dict | None = None) -> None:
        """Record the native admission/session id. Allowed from any fence: it is an observation of
        work already accepted by the harness, never a new write to the target."""
        if not session_id:
            raise InvalidEvidence("native session id is empty")
        with self._tx() as db:
            row = db.execute("SELECT state, session_id, native FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if not row:
                raise LedgerError(f"unknown attempt {attempt_id}")
            if row["session_id"] and row["session_id"] != session_id:
                raise InvalidEvidence(f"attempt {attempt_id} already bound to {row['session_id']}")
            native = json.loads(row["native"])
            native.update(extra or {})
            state = "submitted" if row["state"] in ("authorized", "reconciling") else row["state"]
            db.execute("UPDATE attempts SET session_id=?, native=?, state=?, updated_at=? WHERE attempt_id=?",
                       (session_id, json.dumps(native, sort_keys=True), state, self.clock(), attempt_id))
            self._event(db, "native_bound", {"session_id": session_id, **(extra or {})}, attempt_id=attempt_id)

    def mark_reconciling(self, attempt_id: str, reason: str) -> None:
        with self._tx() as db:
            db.execute("UPDATE attempts SET state='reconciling', reason=?, updated_at=? WHERE attempt_id=? "
                       "AND state IN ('authorized','submitted')", (reason, self.clock(), attempt_id))
            self._event(db, "reconciling", {"reason": reason}, attempt_id=attempt_id)

    def revoke(self, attempt_id: str, readback: dict) -> None:
        """Mark an unresolved attempt as stopped, with the native readback that proves it."""
        if not readback.get("stopped"):
            raise InvalidEvidence("revocation needs a readback showing the worker stopped")
        with self._tx() as db:
            db.execute("UPDATE attempts SET revoked=1, state='held', reason='revoked', resume_trigger='reacquire lease', "
                       "updated_at=? WHERE attempt_id=?", (self.clock(), attempt_id))
            self._event(db, "revoked", readback, attempt_id=attempt_id)

    # -- completion -----------------------------------------------------------------------

    def complete(self, attempt_id: str, lease: Lease, result: dict) -> dict:
        """Store the immutable builder/verifier result for this attempt. Replaying the same result is
        a no-op readback; a different result for a completed attempt is refused."""
        head = str(result.get("head_revision") or "").lower()
        rd = digest(result)
        with self._tx() as db:
            row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if not row:
                raise LedgerError(f"unknown attempt {attempt_id}")
            if row["state"] in ("completed", "independently_verified"):
                if row["result_digest"] == rd:
                    return self._row(row)
                raise CompletionConflict(f"attempt {attempt_id} already completed with another result")
            if row["fence"] != lease.fence or row["task_id"] != lease.task_id or row["role"] != lease.role:
                raise StaleFence(f"attempt {attempt_id} belongs to fence {row['fence']}, not {lease.fence}")
            self._check_fence(db, lease)
            # GUARD:full-sha -- a short or malformed head can never bind evidence.
            if head and not FULL_SHA.match(head):
                raise InvalidEvidence(f"head_revision {head!r} is not a full 40-character SHA")
            db.execute("UPDATE attempts SET state='completed', head_revision=?, evidence=?, result_digest=?, updated_at=? "
                       "WHERE attempt_id=?", (head or None, json.dumps(result, sort_keys=True), rd, self.clock(), attempt_id))
            self._event(db, "completed", {"head_revision": head, "result_digest": rd}, attempt_id=attempt_id)
            row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        return self._row(row)

    def record_verification(self, builder_attempt_id: str, verifier_attempt_id: str, verifier_lease: Lease,
                            verdict: dict) -> dict:
        """Promote a completed builder attempt to independently_verified, only on an exact-head
        APPROVE from a different principal whose own verifier attempt holds the current fence."""
        with self._tx() as db:
            b = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (builder_attempt_id,)).fetchone()
            v = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (verifier_attempt_id,)).fetchone()
            if not b or not v:
                raise LedgerError("unknown builder or verifier attempt")
            if b["role"] != "builder" or v["role"] != "verifier" or v["verifies_attempt"] != builder_attempt_id:
                raise InvalidEvidence("verifier attempt does not verify this builder attempt")
            self._check_fence(db, verifier_lease)
            # GUARD:self-review -- the author cannot mint its own verification.
            if v["lease_owner"] == b["lease_owner"] or (v["session_id"] and v["session_id"] == b["session_id"]):
                raise SelfReview(f"{v['lease_owner']} cannot verify its own attempt")
            if b["state"] not in ("completed", "independently_verified"):
                raise InvalidEvidence(f"builder attempt is {b['state']}, not completed")
            head = str(verdict.get("head_revision") or "").lower()
            if not FULL_SHA.match(head) or head != (b["head_revision"] or ""):
                raise InvalidEvidence("verdict head does not equal the builder's full candidate head")
            now = self.clock()
            db.execute("UPDATE attempts SET state='completed', head_revision=?, evidence=?, result_digest=?, updated_at=? "
                       "WHERE attempt_id=?", (head, json.dumps(verdict, sort_keys=True), digest(verdict), now, verifier_attempt_id))
            if verdict.get("verdict") == "APPROVE_EXACT_HEAD":
                db.execute("UPDATE attempts SET state='independently_verified', updated_at=? WHERE attempt_id=?",
                           (now, builder_attempt_id))
            self._event(db, "verification", {"verdict": verdict.get("verdict"), "head_revision": head,
                                             "verifier": verifier_attempt_id}, attempt_id=builder_attempt_id)
            b = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (builder_attempt_id,)).fetchone()
        return self._row(b)

    # -- reads ----------------------------------------------------------------------------

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        out = dict(row)
        out["native"] = json.loads(out["native"])
        out["evidence"] = json.loads(out["evidence"] or "{}")
        return out

    def attempt(self, attempt_id: str) -> dict:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if not row:
            raise LedgerError(f"unknown attempt {attempt_id}")
        return self._row(row)

    def attempts(self, task_id: str | None = None) -> list[dict]:
        with closing(self._connect()) as db:
            q = "SELECT * FROM attempts" + (" WHERE task_id=?" if task_id else "") + " ORDER BY created_at"
            rows = db.execute(q, (task_id,) if task_id else ()).fetchall()
        return [self._row(r) for r in rows]

    def events(self, attempt_id: str | None = None) -> list[dict]:
        with closing(self._connect()) as db:
            q = "SELECT * FROM events" + (" WHERE attempt_id=?" if attempt_id else "") + " ORDER BY seq"
            rows = db.execute(q, (attempt_id,) if attempt_id else ()).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def to_contract(self, attempt_id: str) -> dict:
        """Render an attempt as a ``contracts/attempt.schema.json`` document."""
        a = self.attempt(attempt_id)
        t = self.task(a["task_id"])
        with closing(self._connect()) as db:
            lease = db.execute("SELECT owner, fence, expires_at FROM leases WHERE task_id=? AND role=?",
                               (a["task_id"], a["role"])).fetchone()
        disp: dict[str, Any] = {"state": a["state"]}
        if a["state"] == "held":
            disp.update(reason=a["reason"], resume_trigger=a["resume_trigger"])
        elif a["reason"]:
            disp["reason"] = a["reason"]
        doc = {
            "schema_version": "vol.attempt/v0",
            "attempt_id": a["attempt_id"],
            "task": {"task_id": t["task_id"], "repo": t["repo"], "issue": t["issue"],
                     "base_revision": t["base_revision"], "goal_lock": {**t["goal_lock"], "digest": t["goal_digest"]}},
            "role": a["role"],
            "lease": {"owner": a["lease_owner"], "fence": a["fence"],
                      "expires_at": _iso(lease["expires_at"])
                      if lease and lease["fence"] == a["fence"] and lease["owner"] else None},
            "submit_intent_id": a["submit_intent_id"],
            "native": {**a["native"], "session_id": a["session_id"]},
            "head_revision": a["head_revision"],
            "evidence": a["evidence"],
            "disposition": disp,
        }
        if a["verifies_attempt"]:
            doc["verifies_attempt"] = a["verifies_attempt"]
        return doc
