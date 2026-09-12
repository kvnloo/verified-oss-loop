# Mature-repo onboard (`--layout mature`)

Greenfield onboard writes `AGENTS.md` and kit skills at the repo root. That is wrong for a fork that already has contribution docs (Hermes, other mature trees).

`--layout mature` (pass the flag; do not infer it from a later greenfield re-run):

- Writes the kit under `.verified-oss-loop/` (inventory, rollout, kit skills).
- Writes `docs/verified-oss-loop.md` as the pointer.
- Does **not** replace `AGENTS.md`, `CONTRIBUTING.md`, or `SECURITY.md`.
- Does **not** copy kit skills into `skills/` (those stay `source: local`).
- Does **not** scrape issue trackers. Clustering uses a local JSON fixture, max 8 in the smoke fixture, cap 64.
- `--with-pages` still copies under `.verified-oss-loop/` (`pages-url-map.py`). Live site is `main`; nightly is `{base}nightly/` not `{base}preview/nightly/`.

```bash
./bin/oss-onboard /path/to/mature-fork --layout mature
```
