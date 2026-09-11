# Orient

Find the existing shape before you edit. Do not rewrite from a generated wiki.

This kit is the protocol plus templates, not an application. The same chain applies in a target repo.

## First 60 seconds

1. Read root `AGENTS.md` and `CONTRIBUTING.md`. Search open issues and PRs.
2. If GitNexus MCP tools are already present: `query` the concept, `context` on the symbol, `impact` before the first edit. Do not run `gitnexus analyze` or `setup` unless a human asked.
3. Else if Serena (or another LSP MCP) is present: `find_symbol`, then `find_referencing_symbols`.
4. Else: `rg` the name, open the files, optionally `ast-grep` for a structural pattern.
5. For a third-party library API, use Context7 or upstream docs. Do not guess signatures from memory.
6. Name the blast radius in one sentence (who calls this, which tests, which sibling surfaces). Then edit.

DeepWiki, cluster dumps, and packed trees (repomix/gitingest) are orientation only. They are not evidence.

Catalog and licenses: `docs/agent-onboarding.md`.

## Do not

- Index the repo or rewrite `AGENTS.md` / `CLAUDE.md` as a side effect of onboarding.
- Vendor GitNexus (PolyForm Noncommercial) into an Apache-2.0 tree.
- Treat a wiki answer as `tests.green`.
- Invent a second loop named after a tool.
