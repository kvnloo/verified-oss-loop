# Quality at scale

This is **not a second loop**. [SPEC.md](../SPEC.md) still owns claims, receipts, and merge of `main`/`dev`. [rollout.md](rollout.md) only chooses channel speed. [quality-bots.md](quality-bots.md) catalogs Level-1 bots. This file is the **TAKE / SKIP** from long-lived OSS: how they kept quality when contributor volume (now agent volume) exploded.

Principle: **compute replaces attempts; humans keep commitments to users.** Generation is cheap. Merge attention is not. [kerdoios](https://github.com/kvnloo/kerdoios) already allots scarce compute. Factory `github_writes=0` until Linear Todo is the same gate.

Do not dump these projects' bots, mailing lists, or Forgejo/Buildbot into every onboard target. Steal **gates and channel policy**.

## Linux-shaped channels

Kernel process: [submitting-patches](https://docs.kernel.org/process/submitting-patches.html), [2.Process](https://docs.kernel.org/process/2.Process.html), [stable-kernel-rules](https://docs.kernel.org/process/stable-kernel-rules.html).

| Kernel | This kit |
|---|---|
| Subsystem maintainer trees | Feature PRs → **`preview`** |
| **linux-next** (~400 trees, daily) | **`nightly`** (integration soak) |
| Mainline **`-rc`** (fixes; regressions revert) | **`dev`** (gated) |
| Mainline release | **`main`** |
| **`-stable` / LTS** (already in mainline, small, tested) | **`scheme: stable`** |
| `MAINTAINERS` + `get_maintainer.pl` | CODEOWNERS + labeler |
| Signed-off-by / DCO | evidence receipt + exact head |
| NACK / Patchwork rejected | DISCARD |
| “Do not email Linus” | workers never merge `main`/`dev` |
| Merge window then freeze | Kerdoios allotment + Linear Todo |

**TAKE:** human-only production merge; preview/nightly absorb chaos; SoB-shaped receipts; route by path; ignore drive-by floods (lkml already taught this).

**SKIP:** email-first intake; rewriting history in the integration tree; `drivers/staging/` as a parallel product; Linus-as-sole-merge; bulk automerge past the merge window.

## Canon (copy ritual, not stars)

Substrate: Linux, LLVM, GCC, glibc/musl, Git, QEMU, PostgreSQL, SQLite, OpenBSD, FreeBSD, OpenSSL/LibreSSL.

Languages: CPython ([bedevere](https://github.com/python/bedevere), [PEP 13](https://peps.python.org/pep-0013/)), rust-lang ([bors](https://forge.rust-lang.org/infra/docs/bors.html), [rfcbot](https://github.com/rust-lang/rfcs), [triagebot](https://forge.rust-lang.org/triagebot/pr-assignment.html)), Go.

Ship continuously: Debian (`unstable` → freeze → `testing`), Nixpkgs (Hydra `staging` → `master`), Arch (rolling), Chromium ([CQ](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/infra/cq.md) + [OWNERS](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/code_review_owners.md)), Kubernetes ([Prow/Tide](https://docs.prow.k8s.io/docs/components/core/tide/), [OWNERS](https://www.kubernetes.dev/docs/guide/owners/)).

Vertical: Home Assistant (hassfest), LiteLLM (Greptile/Codecov/CodSpeed around a human), FFmpeg, Blender (Buildbot on demand), systemd (ASan/UBSan/OSS-Fuzz; humans merge).

558 `kvnloo/*` **forks** are a library of *their* process. Origin OSS keeps their CONTRIBUTING. Never `oss-onboard` labels onto them.

## TAKE vs SKIP (compressed)

| Steal | Do not take |
|---|---|
| Path owners + `/hold` ([k8s](https://www.kubernetes.dev/docs/guide/owners/)) | Tide / Bors / Homu as a **worker** merge key |
| `/lgtm` ≠ `/approve` (review vs land) | Author self-approve |
| Receipt-before-review ([bedevere](https://github.com/python/bedevere)) | Full Bedevere FSM + backport bots in every target |
| CI on “PR ⊕ current base” ([bors](https://forge.rust-lang.org/infra/docs/bors.html)) | Worker `@bors merge` |
| One logical change, one `head_revision` ([LLVM squash](https://www.llvm.org/docs/GitHub.html)) | Stacked-diff tooling wars |
| Stage labels (Commitfest vocabulary as GitHub labels) | Commitfest app / CFBot as a second loop |
| In-repo validators (hassfest-shaped), run locally | Vendor GitHub Apps in `oss-onboard` |
| Manifest- or path-derived CODEOWNERS ([HA](https://github.com/home-assistant/core/blob/dev/CODEOWNERS)) | Blender-style comment bots without Buildbot; FFmpeg Fairy as required |
| Optional SaaS review as **evidence** | Greptile ≥4/5 or Agent Shin auto-close as merge law |
| Debian/Nix **promotion** (unstable vs staging vs stable) | Silent ABI churn on `scheme: stable` |
| Chromium sheriff **revert** on red | CQ overload / unbatched dep bumps on `main` |
| OpenBSD peer OK on shared ports | Untested rolling of libraries |
| Security embargo ([Chromium](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/security-labels.md), kernel `security-bugs.rst`) | Public vuln issues; SPEC §8 |

## Infinite compute: where it goes

Spend it on **`preview` / `nightly` only**: matrix CI, fuzz/mutation, flake quarantine, auto-revert on red, independent AI review of the **exact head**, automated bisect, linux-next-style path integration before promote.

**Never:** automerge `dev`/`main`; land API/ABI without CODEOWNERS/RFC; merge through embargo; stack four comment bots (notification fatigue = Dependabot/lkml); mint `claimable` from empty queues.

Bottlenecks that do not go away with more GPUs: attention, burnout, revert cost, ABI freeze, security judgment, bisect/flakes, docs lag. [linux-next](https://lore.kernel.org/linux-next/) exists because integration is a human-shaped problem.

## This household (do not split-brain)

| Layer | Owns | Must not own |
|---|---|---|
| [oss-factory](https://github.com/kvnloo/oss-factory) | HITL columns, traction (`4*merged − spray`) | Claim leases, merge, a second SPEC |
| **this kit** | Contract, onboard, rollout | Linear triage, compute routing |
| [frontier-kb](https://github.com/kvnloo/frontier-kb) | Research memory | Origin writes until Todo |
| [kerdoios](https://github.com/kvnloo/kerdoios) | Compute allotment | Dispatch / LLM gateway |
| [hermes-keel](https://github.com/kvnloo/hermes-keel) | Capability + evidence invariants | Kanban truth |
| [aodl](https://github.com/kvnloo/aodl) | Fail-closed IR | Scheduler |
| [dash](https://github.com/kvnloo/dash) / [company-os](https://github.com/kvnloo/company-os) | HUD / phone bridge | Issue tracker, merge bot |

If every repo mints claims, the factory `spray` term is the metric. One `head_revision` per receipt. Re-run `oss-onboard` on opted-in children when this kit moves (kerdoios `prompt.md` still pointed at `origin/main` after rollout landed here).
