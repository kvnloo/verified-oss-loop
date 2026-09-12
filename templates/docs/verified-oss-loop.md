# Verified OSS Loop ({{PROJECT}})

This repository already has its own `AGENTS.md`. The Verified OSS Loop kit lives under `.verified-oss-loop/` so onboard does not replace project instructions or dump kit skills over existing `source: local` skills.

Workers never merge `main` or `dev`. `github_writes=0` on origin until a human authorizes origin writes. Open PRs on the **fork** only.

## Kit paths

- Inventory / rollout: `.verified-oss-loop/`
- Kit skills (not copied into `skills/`): `.verified-oss-loop/skills/`
- Similar-issue clustering (local fixture only, cap 64): `.verified-oss-loop/scripts/cluster-similar-issues.py`
- Pages URL map: `.verified-oss-loop/pages-url-map.py` (live site is `main`; nightly is `{base}nightly/` not `{base}preview/nightly/`)

## Commands

| Layer | Command |
|---|---|
| Unit | `{{UNIT_CMD}}` |
| Mutation | `{{MUTATOR_CMD}}` |
| Runtime | `{{RUNTIME_CMD}}` |

```bash
python3 .verified-oss-loop/rollout.py show
python3 .verified-oss-loop/pages-url-map.py show
python3 .verified-oss-loop/scripts/cluster-similar-issues.py tests/fixtures/issues-tiny.json
```

Repo: {{REPO_URL}}
