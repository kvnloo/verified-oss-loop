# Agentic onboarding tools

This is **not a second loop**. [SPEC.md](../SPEC.md) remains the contribution contract. Tools here help a worker **orient** and keep the diff small. They do not merge. They do not redefine the roadmap.

`oss-onboard` copies `skills/orient` and `skills/anti-slop`. It does **not** run `npx gitnexus analyze`, does not vendor GitNexus skills/hooks, and does not rewrite `AGENTS.md` with a second H1.

Keep root `AGENTS.md` lean. Codex and similar clients truncate around 32 KiB. Point at skills instead of a manifesto.

## Catalog (if present — do not install unless a human asked)

| Tool | Role | License | Copied by this kit? |
|---|---|---|---|
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | Local knowledge graph + MCP (`query`, `context`, `impact`, `trace`, `detect_changes`, `rename`, `cypher`, plus `api_impact` / `route_map` / `tool_map` when indexed) | PolyForm Noncommercial 1.0.0 (commercial use needs their license) | **No.** Catalog + “if MCP already there”. Never copy source or generated skills |
| [Serena](https://github.com/oraios/serena) | LSP symbol retrieve/edit MCP | MIT | Catalog. Prefer this OSS path when a graph tool is not already installed |
| [Context7](https://github.com/upstash/context7) | Versioned *library* docs, not a repo graph | MIT | Catalog. Use for third-party APIs |
| DeepWiki (Cognition, hosted) | Orientation wiki | Hosted | Catalog. Not evidence. Do not treat it as a receipt |
| [repomix](https://github.com/yamadashy/repomix) / [gitingest](https://github.com/cyclotruc/gitingest) | One-shot packed tree for a first read | MIT | Catalog. Do not paste a whole pack into every turn |
| [ast-grep](https://github.com/ast-grep/ast-grep) | Structural search when the graph is missing | MIT | Catalog. Fallback after `rg` |
| [Aider](https://github.com/Aider-AI/aider) repo map | Local token-bounded map | Apache-2.0 | Catalog. Not a claim lease |
| [pstack](https://github.com/cursor/plugins/tree/main/pstack) | Cursor plugin: `/poteto-mode`, `/how`, `/unslop`, playbooks | MIT (Lauren Tan) | **No dump.** Pointer skill `skills/pstack`. If already installed, use it. Extra plugin files are `local` |
| Dr Eggbot | Grok Bot that authors other bots/skills (one job, unslopped, verified) | Marketplace / pstack | **No dump.** Pointer skill `skills/dr-eggbot`. Not in oss-factory |
| [agents.md](https://agents.md/) | Portable agent file | Convention | Already the kit’s `AGENTS.md` |

## GitNexus: use, do not vendor

If the workspace already exposes GitNexus MCP tools:

1. `query` the concept or symbol.
2. `context` on the specific symbol (callers, callees, process participation).
3. `impact` before editing (blast radius). `detect_changes` after a local diff.
4. Read the files the graph named. Then edit.

Do **not**:

- Run `npx gitnexus analyze` or `gitnexus setup` from `oss-onboard` or an unattended claim. `analyze` indexes **and** may write `AGENTS.md` / `CLAUDE.md`, install hooks, and generate area skills — a second instruction surface.
- Copy GitNexus into this Apache-2.0 kit or into `frontier-kb`.
- Treat a generated wiki or cluster dump as `tests.green`.
- Invent a parallel process named after the tool.

Maintainers who want GitNexus install it themselves (`gitnexus analyze` / `setup` in that repo). Workers check for the tools; they do not bootstrap the indexer.

## Fallback chain

Same order as `skills/orient/SKILL.md`:

1. GitNexus MCP if the tools exist.
2. Serena `find_symbol` / `find_referencing_symbols` (or the project’s LSP).
3. `rg` + open the files. `ast-grep` for structural patterns.
4. Context7 (or upstream docs) for library APIs — not for this repo’s own types.

## Skills this kit copies

| Skill | Job |
|---|---|
| `skills/orient/SKILL.md` | First 60s: graph or search, then blast radius, then edit |
| `skills/anti-slop/SKILL.md` | Patterns vs anti-patterns; smallest complete change |
| `skills/pstack/SKILL.md` | Use pstack if present; never merge; never vendor the plugin |
| `skills/dr-eggbot/SKILL.md` | Author one skill/bot; anti-jobs; healthcheck; no marketplace dump |
| `skills/autodevelop/SKILL.md` | One claim; calls orient → TDD → anti-slop → receipt |
| `skills/tdd/SKILL.md` | Fail, then pass |
| `skills/verify/SKILL.md` | Receipt; mutation `n/a` when the stack has none |

Kit vs local provenance and re-sync: [kit-inventory.md](kit-inventory.md). Quality bots: [quality-bots.md](quality-bots.md). Factory HITL: [HITL.md](../HITL.md) (adapter: [factory.md](factory.md)).
