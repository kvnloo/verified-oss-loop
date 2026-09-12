#!/usr/bin/env python3
"""Map git refs to publish URL paths. Stdlib only. Does not merge.

Git channel names (preview, nightly, dev, main) are not URL folders.
Catch-all prefixes must not be named preview or nightly.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "verified-oss-loop.pages-url-map.v1"
RESERVED = ("preview", "nightly", "dev", "main")
DEFAULT_FEATURE_PREFIX = "wip"
DEFAULT_CHANNELS: dict[str, str | None] = {
    "main": "",
    "nightly": "nightly",
    "preview": "next",
    "dev": None,
}
CONFIG_REL = Path(".verified-oss-loop") / "pages-url-map.yml"
PAGES_CANDIDATES = (
    Path(".github") / "workflows" / "pages.yml",
    Path(".github") / "workflows" / "pages.yaml",
    Path("scripts") / "build-pages.py",
)
SKIP_WORKFLOW_NAMES = {
    "automerge-preview.yml",
    "automerge-nightly.yml",
    "promote-preview.yml",
    "pages-channels.md",
}

# Catch-all dest construction: every non-main branch under /preview/<slug>/
CATCHALL_RES = (
    re.compile(r"preview/<"),
    re.compile(r"preview/\{"),
    re.compile(r"preview/\$\{"),
    re.compile(r"preview/\$[A-Za-z_]"),
    re.compile(r"/preview/\$"),
    re.compile(r"""['"]/?preview/['"]"""),
    re.compile(r"nightly/<"),
    re.compile(r"nightly/\{"),
    re.compile(r"nightly/\$\{"),
    re.compile(r"nightly/\$[A-Za-z_]"),
    re.compile(r"/nightly/\$"),
    re.compile(r"""['"]/?nightly/['"]"""),
)


def normalize_branch(ref: str) -> str:
    b = (ref or "").strip()
    for prefix in ("refs/heads/", "refs/remotes/origin/", "refs/remotes/", "origin/"):
        if b.startswith(prefix):
            b = b[len(prefix) :]
            break
    return b


def slug(branch: str) -> str:
    return normalize_branch(branch).replace("/", "--")


def normalize_base(base: str) -> str:
    b = (base or "/").strip() or "/"
    if not b.startswith("/"):
        b = "/" + b
    if not b.endswith("/"):
        b += "/"
    return b


def join_base(base: str, dest: str) -> str:
    root = normalize_base(base)
    dest = (dest or "").strip("/")
    if not dest:
        return root
    return f"{root}{dest}/"


def unpublished(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("null", "~", "omit", "none")


def parse_channel_val(raw: str) -> str | None:
    v = raw.strip().strip("'\"")
    if unpublished(v):
        return None
    return v


def default_config() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "feature_prefix": DEFAULT_FEATURE_PREFIX,
        "channels": dict(DEFAULT_CHANNELS),
    }


def load_config(root: Path) -> dict[str, Any]:
    data = default_config()
    path = root / CONFIG_REL
    if not path.is_file():
        return data
    in_channels = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if in_channels and ":" in line:
                key, val = line.strip().split(":", 1)
                key = key.strip()
                if key:
                    data["channels"][key] = parse_channel_val(val)
            continue
        in_channels = False
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if key == "schema" and val:
            data["schema"] = val.strip("'\"")
        elif key == "feature_prefix":
            data["feature_prefix"] = val.strip("'\"") or DEFAULT_FEATURE_PREFIX
        elif key == "channels":
            in_channels = True
    return data


def dest_for_branch(branch: str, cfg: dict[str, Any]) -> str | None:
    name = normalize_branch(branch)
    channels: dict[str, str | None] = data_channels(cfg)
    if name in channels:
        return channels[name]
    prefix = str(cfg.get("feature_prefix") or DEFAULT_FEATURE_PREFIX).strip("/") or DEFAULT_FEATURE_PREFIX
    return f"{prefix}/{slug(name)}"


def data_channels(cfg: dict[str, Any]) -> dict[str, str | None]:
    ch = dict(DEFAULT_CHANNELS)
    extra = cfg.get("channels") or {}
    if isinstance(extra, dict):
        for k, v in extra.items():
            ch[str(k)] = None if unpublished(v) else str(v)
    return ch


def url_for_branch(branch: str, base: str, cfg: dict[str, Any]) -> str | None:
    dest = dest_for_branch(branch, cfg)
    if dest is None:
        return None
    return join_base(base, dest)


def path_nests_reserved(url: str) -> bool:
    segs = [s for s in url.split("/") if s]
    if "preview" in segs:
        return True
    if any(s in RESERVED for s in segs[:-1]):
        return True
    reserved_hits = [s for s in segs if s in RESERVED]
    return len(reserved_hits) > 1


def map_errors(cfg: dict[str, Any], base: str) -> list[str]:
    errors: list[str] = []
    prefix = str(cfg.get("feature_prefix") or "").strip("/")
    if prefix in RESERVED:
        errors.append(
            f"feature_prefix {prefix!r} is a git channel name; use wip (not /{prefix}/<slug>/)"
        )
    channels = data_channels(cfg)
    preview_dest = channels.get("preview")
    if preview_dest is not None:
        segs = [s for s in str(preview_dest).split("/") if s]
        if "preview" in segs:
            errors.append("git branch preview must not publish under a folder named preview; use next")
    for name in RESERVED:
        url = url_for_branch(name, base, cfg)
        if url is None:
            continue
        if path_nests_reserved(url):
            errors.append(f"channel {name} nests a reserved name: {url}")
        if "/preview/nightly/" in url or "/preview/preview/" in url:
            errors.append(f"forbidden URL {url}")
    return errors


def strip_code_comments(text: str) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.lstrip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        if "#" in raw:
            in_s = False
            q = ""
            buf: list[str] = []
            i = 0
            while i < len(raw):
                ch = raw[i]
                if in_s:
                    buf.append(ch)
                    if ch == q and (i == 0 or raw[i - 1] != "\\"):
                        in_s = False
                    i += 1
                    continue
                if ch in ("'", '"'):
                    in_s = True
                    q = ch
                    buf.append(ch)
                    i += 1
                    continue
                if ch == "#":
                    break
                buf.append(ch)
                i += 1
            raw = "".join(buf)
        out.append(raw)
    return "\n".join(out)


def iter_pages_files(root: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for rel in PAGES_CANDIDATES:
        p = root / rel
        if p.is_file():
            found.append(p)
            seen.add(p.resolve())
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        for p in sorted(wf.iterdir()):
            if p.suffix.lower() not in {".yml", ".yaml"}:
                continue
            if "pages" not in p.name.lower():
                continue
            if p.name in SKIP_WORKFLOW_NAMES:
                continue
            if p.resolve() in seen:
                continue
            found.append(p)
    return found


def catchall_hits(text: str) -> list[str]:
    body = strip_code_comments(text)
    hits: list[str] = []
    for rx in CATCHALL_RES:
        if rx.search(body):
            hits.append(rx.pattern)
    return hits


def check_root(root: Path, base: str) -> list[str]:
    cfg = load_config(root)
    errors = map_errors(cfg, base)
    for path in iter_pages_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"cannot read {path}: {exc}")
            continue
        hits = catchall_hits(text)
        if hits:
            rel = path.relative_to(root).as_posix()
            errors.append(
                f"{rel} nests git channels under a catch-all folder "
                f"(forbidden: {join_base(base, 'preview/nightly')} "
                f"{join_base(base, 'preview/preview')}; "
                f"hoist channels, feature prefix wip)"
            )
    return errors


def cmd_show(root: Path, base: str) -> int:
    cfg = load_config(root)
    channels = data_channels(cfg)
    print(f"schema={cfg.get('schema') or SCHEMA}")
    print(f"base={normalize_base(base)}")
    print(f"feature_prefix={cfg.get('feature_prefix') or DEFAULT_FEATURE_PREFIX}")
    for name in ("main", "nightly", "preview", "dev"):
        dest = channels.get(name)
        print(f"{name}={'omit' if dest is None else dest}")
    return 0


def cmd_path(branch: str, base: str, root: Path) -> int:
    cfg = load_config(root)
    url = url_for_branch(branch, base, cfg)
    if url is None:
        return 0
    print(url)
    return 0


def cmd_check(root: Path, base: str) -> int:
    errors = check_root(root, base)
    if errors:
        print("pages-url-map check failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(
            "fix: main→{base}  nightly→{base}nightly/  preview→{base}next/  "
            "features→{base}wip/<slug>/  (preview git ≠ /preview/)",
            file=sys.stderr,
        )
        return 1
    print("ok: pages URL map does not nest git channels")
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="repo root (config + Pages files)")
    common.add_argument("--base", default="/", help="site base path, e.g. / or /aodl/")
    p = argparse.ArgumentParser(description="Git channel ≠ publish URL (Pages map)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", parents=[common])
    pa = sub.add_parser("path", parents=[common])
    pa.add_argument("--branch", required=True)
    sub.add_parser("check", parents=[common])
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "show":
        return cmd_show(root, args.base)
    if args.cmd == "path":
        return cmd_path(args.branch, args.base, root)
    return cmd_check(root, args.base)


if __name__ == "__main__":
    sys.exit(main())
