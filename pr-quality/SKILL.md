---
name: pr-quality
description: Creates and reviews high-signal pull requests using exact diff accounting, evidence-backed testing, behavior/performance/risk analysis, adjacent-behavior and shared-consumer blast-radius checks, and staff-level solution review. Use when preparing, updating, or reviewing a PR; drafting a PR body; deciding whether a change is ready for review; or checking whether the chosen solution is the right one rather than merely correct.
---

# PR Quality

Create pull requests that let a reviewer answer, quickly and with evidence:

1. What changed, and why?
2. How much production code changed versus tests and configuration?
3. What proves the change works?
4. What behavior, performance, compatibility, and adjacent surfaces could change?
5. What happens to downstream consumers?
6. Is this the right solution, not merely a working solution?

Do not invent evidence. If something was not measured, run the relevant check or say that it was not measured or not tested.

## Before drafting the PR

Read the repository before imposing this skill. Inspect, when present:

- `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`, Cursor rules, and repository instructions;
- `.github/pull_request_template.md` and other PR templates;
- package/test/build scripts;
- recent representative PRs if accessible;
- issue/tracker conventions;
- the repository's default/base branch and actual diff.

Repository conventions win when they conflict with cosmetic parts of this skill. Keep the substantive evidence requirements.

Do not merge, deploy, publish, or perform another hard-to-reverse outward action merely because the PR is ready. Do those only when explicitly requested.

## 1. Establish the change and issue context

State the problem before describing the implementation. Determine:

- problem or user-visible need;
- root cause, if verified;
- intended behavior after the change;
- issue/ticket(s), if the repository uses them;
- important non-goals or deliberately unresolved follow-ups.

Never invent a ticket number or title.

### Legacy Jira format

When working in a repository that uses the recovered `DEV-XXXXX` convention, format each ticket exactly as:

```text
Fixes [DEV-XXXXX] — <ticket title>
```

One ticket per line. Example:

```text
Fixes [DEV-16544] — Coherence "split by tags": purple shadow/range band shows impossible values far above actual data
Fixes [DEV-16543] — Coherence "split by tags": series labeled with stream name instead of tag
```

For GitHub Issues, Linear, or another tracker, follow that repository's normal closing/reference syntax instead.

## 2. Account for the diff exactly

Before finalizing the PR body, get exact per-file additions/deletions from the final branch diff. Prefer the repository's actual base branch.

Typical commands:

```bash
git fetch origin
git diff --numstat origin/main...HEAD
```

or:

```bash
git diff --numstat origin/develop...HEAD
```

You may run `scripts/loc_breakdown.py --base <base>` from this skill to generate a first-pass table. Review its classifications manually before using them.

Every meaningful PR should separate at least:

- **Fix** — production implementation;
- **Fix (config)** — tooling/build/configuration changes;
- **Tests** — test code and fixtures.

Add another category such as **Docs** only when it materially improves clarity. Never combine production and tests into one aggregate number.

Render per-file rows, category subtotals, and an overall total:

```markdown
| Category | File | + | − |
|---|---|---:|---:|
| Fix | src/example.ts | 42 | 18 |
| **Fix subtotal** | | **42** | **18** |
| Tests | src/example.test.ts | 137 | 0 |
| **Tests subtotal** | | **137** | **0** |
| **Total** | | **179** | **18** |
```

Add a sentence below the table giving the net production-code change when useful:

```text
Net production change: +24 lines.
```

LOC is not a productivity metric. The purpose is to keep a large test/config diff from obscuring the actual production change.

## 3. Treat testing as evidence, not a checkbox

Do not write only `tests pass`. Report the strongest evidence actually available for the change.

### Ordinary tests

Include:

- exact command(s) run;
- relevant test/suite counts when the runner reports them;
- runtime when useful;
- focused tests plus full-suite status when both were run.

### Coverage

Report coverage only when measured. Do not imply coverage proves correctness.

### Property-based testing

When appropriate, report:

- properties added or changed;
- the invariant each property expresses;
- meaningful counterexamples discovered;
- whether important generated failures were preserved as deterministic regression tests.

A property that merely says `does not throw` is smoke coverage, not a full behavioral specification.

### Mutation testing

When available and valuable, report:

- exact mutation scope;
- killed/survived counts or score for that scope;
- meaningful surviving mutants;
- equivalent/tooling/unreachable survivors and why they remain;
- whether mutation is local/on-demand or a CI gate.

Do not chase 100% mechanically. An explained equivalent mutant is better than a meaningless test written solely to move a score.

### Integration, browser, device, and manual verification

State what was actually verified: API/integration behavior, browser/E2E behavior, visual regression, supported browser/device behavior, production-like/customer-data verification, and manual flows.

Unit tests do not prove visual or browser behavior they cannot observe.

### Performance

If the change is performance-sensitive, include real before/after evidence such as timings, query counts, payload size, CPU/memory, network requests, traces, and benchmark conditions.

Do not use adjectives such as `faster` or `more efficient` without data when data can reasonably be obtained.

For detailed testing guidance, read `references/testing-evidence.md`.

## 4. Answer the review questions

Every substantive PR should contain a `## Review questions` section answering all seven questions. If a question genuinely does not apply, say `N/A` and why rather than deleting it.

1. **Does this fix/feature change existing behavior, or is it additive?**
   Name behavior-changing parts separately from purely additive parts.

2. **What is the performance impact — positive or negative?**
   Use real measurements when relevant. If it was not measured because the path is not performance-sensitive, say so.

3. **What bugs or issues could we be missing here?**
   List edge cases, unverified assumptions, rollback/compatibility concerns, and known limitations.

4. **What else was fixed/implemented here that may not be obvious or properly documented?**
   Surface incidental or bundled behavior instead of hiding it in the diff.

5. **Will this functionality/fix work on iPhone Safari or the project's comparable constrained/mobile environment?**
   For web work, consider pointer/touch events, layout/container behavior, media/canvas behavior, browser support, and actual device testing. If not device-tested, say so. For non-web projects, adapt this to the most constrained supported runtime and state the adaptation explicitly.

6. **Does this alter any existing, adjacent behavior that shares the same component, element, event surface, API, state, persistence layer, or execution path?**
   Name neighboring behavior and state how it was verified. Example: drag-to-scrub must not break click-to-seek on the same timeline.

7. **If this ships in a shared package/library/service, what is the downstream blast radius when other consumers pick up the change?**
   Identify actual consumers. For each affected consumer classify propagation as **inert**, **purely additive**, or **behavior-changing**. Verify consumer usage from code/dependency data when available; do not assume.

For a compact review-only version, read `references/review-checklist.md`.

## 5. Perform a staff-level solution review before finalizing

Do not stop at `the code works`.

### Symptom vs. disease

Does this address the root class of problem or only the observed instance? It can be acceptable to fix only the instance, but name the broader class and any deliberate follow-up.

### Detect vs. prevent

Prefer designs that make invalid states or configuration drift impossible over tests that merely detect the next occurrence.

Smell:

```text
same magic value copied into five files
+ test that checks they stay equal
```

Prefer, when feasible:

```text
one source of truth
+ all consumers derive from it
```

### Time bombs

Identify temporary caps, compatibility pins, migrations, deprecations, or assumptions that will predictably expire. Document the follow-up rather than letting a future incident rediscover it.

### CI and efficiency

Look for:

- the same behavior tested redundantly several ways without added decision value;
- fragile or high-maintenance scaffolding;
- changed paths with no real CI coverage;
- tests configured so failures do not fail the build;
- expensive checks being made universal when a scoped/local check is more appropriate.

### Under-justified judgment calls

Challenge version floors, caps, thresholds, timeouts, concurrency limits, cache durations, retry counts, compatibility drops, and other reasonable-looking numbers. Use the value the technology/product actually requires and explain why.

### Right solution

Conclude internally:

```text
Is this solution effective, efficient, maintainable, and performant for the actual problem?
```

If not, improve the approach before polishing the PR description.

## 6. Verify claims against the real execution path

A plausible fix is not enough. Where feasible:

- verify that the changed code is actually on the live/runtime path;
- use source, instrumentation, traces, or a reproduction to prove it;
- distinguish `verified` from `inferred`;
- do not claim a production/customer defect is fixed solely because a unit test passes.

If runtime verification disproves the original fix path, say so and correct the approach before declaring success.

## 7. Draft the PR body

Use the repository's required template if one exists, while preserving the evidence above. Otherwise start from `assets/pr-body-template.md`.

Keep the body scannable. Prefer concrete evidence over long narrative.

### Acronyms

If the title or body uses an acronym or initialism, end the body with a dedicated `## Acronyms` section. Omit the section when there are none.

- List each acronym once, alphabetically, as `- **LOC** - lines of code`.
- Include common ones such as `API` and `CI`; the section is for any reader, not only those who already know the term.
- Do not expand an acronym where it appears. Write `LOC`, not `lines of code (LOC)`, and leave the meaning to the section.
- Skip acronyms that appear only in the template's own headings, or in code, file paths, or ticket keys.
- Keep this section last, after `## Known limitations / follow-ups`.

## 8. Final readiness check

- [ ] Problem and verified root cause are clear.
- [ ] Ticket/issue reference follows repository convention.
- [ ] LOC table uses the final branch diff and per-file counts.
- [ ] Production, config, and tests are separated.
- [ ] Test claims match commands/results actually run.
- [ ] Property/mutation claims include scope and meaningful caveats.
- [ ] Performance claims have measurements when relevant.
- [ ] All seven review questions are answered.
- [ ] Adjacent behavior has been considered and verified where relevant.
- [ ] Shared-consumer blast radius was checked rather than guessed.
- [ ] Staff-level solution review challenged the approach itself.
- [ ] Known limits, unverified areas, and follow-ups are stated.
- [ ] No claim overstates what the evidence proves.
- [ ] Acronyms are not expanded inline and are all listed in a final `## Acronyms` section.
- [ ] No merge/deploy/publish is performed without explicit instruction.

## Output behavior

When asked to prepare a PR:

1. inspect the repository and final diff;
2. run or collect the strongest reasonable verification;
3. generate/review the LOC table;
4. perform the seven review questions and staff-level solution check;
5. return a complete copy-paste PR body;
6. if tools and authorization permit and the user asked to create/update the PR, do so;
7. do not merge unless explicitly asked.

When asked to review a PR, return high-signal findings first. Judge both correctness and whether the approach is the right solution.
