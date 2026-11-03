"""Validate documents against the subset of JSON Schema used in ``contracts/``. Stdlib only.

Supports: type (incl. lists), const, enum, pattern, minLength, minimum, required, properties,
additionalProperties=false, items, oneOf, $ref to #/$defs, if/then. Unknown keywords are ignored,
so keep contracts inside this subset (tests check the example validates and a broken one fails).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
          "boolean": bool, "null": type(None)}


def _is(value, t: str) -> bool:
    if t in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[t])


def validate(doc, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = root or schema
    errs: list[str] = []
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return validate(doc, root["$defs"][name], root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is(doc, t) for t in types):
            return [f"{path}: expected {types}, got {type(doc).__name__}"]
    if "const" in schema and doc != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: {doc!r} not in {schema['enum']}")
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errs.append(f"{path}: {doc!r} does not match {schema['pattern']}")
        if len(doc) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than {schema['minLength']}")
    if _is(doc, "number") and "minimum" in schema and doc < schema["minimum"]:
        errs.append(f"{path}: below minimum {schema['minimum']}")
    if "oneOf" in schema:
        ok = sum(1 for s in schema["oneOf"] if not validate(doc, s, root, path))
        if ok != 1:
            errs.append(f"{path}: matches {ok} of oneOf, need exactly 1")
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errs.append(f"{path}: missing {key}")
        props = schema.get("properties", {})
        for key, val in doc.items():
            if key in props:
                errs += validate(val, props[key], root, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected property {key}")
        if "if" in schema and not validate(doc, schema["if"], root, path):
            errs += validate(doc, schema.get("then", {}), root, path)
    if isinstance(doc, list) and "items" in schema:
        for i, item in enumerate(doc):
            errs += validate(item, schema["items"], root, f"{path}[{i}]")
    return errs


def main(argv: list[str]) -> int:
    schema = json.loads(Path(argv[0]).read_text())
    rc = 0
    for f in argv[1:]:
        errs = validate(json.loads(Path(f).read_text()), schema)
        print(f"{f}: {'ok' if not errs else '; '.join(errs)}")
        rc |= bool(errs)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
