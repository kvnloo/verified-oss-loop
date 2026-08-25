# Verified OSS Loop

A lightweight, project-neutral protocol for open-source communities that want humans and coding agents to improve a repository in parallel without duplicate work, unverifiable claims, or autonomous merge authority.

## The loop

```text
maintainer roadmap
→ prioritized issue queue
→ bounded claim lease
→ isolated branch/worktree
→ implementation + evidence receipt
→ independent verification
→ maintainer/human merge decision
→ outcome feeds the next roadmap revision
```

This grew from the [Community-wide Distributed Self-Development Loop](https://github.com/AndyMik90/Aperant/discussions/306), then informed [Hermes autoresearch](https://github.com/NousResearch/hermes-agent/issues/5114), [reversible harness refinement](https://github.com/NousResearch/hermes-agent/issues/93306), and household edge-compute proposals across agent runtimes.

## What it adds

Existing systems already cover important parts:

- GitHub Issues/Projects: backlog and roadmap
- [issue-spec](https://github.com/higress-group/issue-spec): proposal/design/implementation DAGs
- [CDEvents](https://github.com/cdevents/spec): delivery events
- [OpenSSF Scorecard](https://github.com/ossf/scorecard): repository security health

Verified OSS Loop adds the missing contribution contract:

- maintainer-owned priority and acceptance
- duplicate-safe claim leases
- isolated execution
- revision-bound evidence
- reproducible RED/GREEN/sabotage/build receipts
- independent review
- KEEP/DISCARD decisions
- explicit human merge authority
- cost/resource accounting without pay-to-win priority

## Principles

1. **Maintainers own direction.** Agents and contributors propose; they do not redefine the roadmap.
2. **Issues are not claims.** Work begins only after policy and duplicate checks.
3. **Claims expire.** Stale contributors cannot block an issue forever.
4. **Every result binds to a revision.** Tests from another head are not evidence.
5. **Tests are necessary, not sufficient.** Build/runtime/user-path proof follows project policy.
6. **Generation and verification are separate.** The implementer does not self-approve.
7. **Workers never merge.** Maintainers or explicitly authorized humans decide.
8. **Failure is useful.** DISCARD receipts preserve why an approach failed.
9. **No ceremonial automation.** Small projects can adopt this with labels and a Markdown receipt.
10. **Project policy wins.** This protocol never overrides CONTRIBUTING, security, AI disclosure, CLA/DCO, or review rules.

## Minimal adoption

A project needs only:

- roadmap or priority document
- issue labels: `priority`, `claimable`, `claimed`, `needs-review`, `blocked`
- claim comment with expiry
- evidence section in the PR template
- one independent reviewer
- human merge gate

See [SPEC.md](SPEC.md) for the complete contracts.

## Scope

This protocol applies to any open-source project. Distributed compute and household-device meshes are a separate optional execution layer for projects that can benefit from them.

## License

Apache-2.0
