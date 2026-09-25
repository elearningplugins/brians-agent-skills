# Brian's Agent Skills

**Engineering judgment, turned into reusable instructions for AI coding agents.**

These are not generic prompt templates.

They are working methods Brian has developed over more than 15 years building, testing, reviewing, releasing, debugging, supporting, and leading software teams, then turned into reusable Agent Skills for Cursor, Claude Code, Codex, and other tools that support `SKILL.md`.

The goal is simple:

**Give an AI coding agent more than instructions for writing code. Give it the engineering habits needed to decide whether the code is actually good.**

## Where these skills come from

Brian's career has crossed the boundaries that normally separate software teams:

* Production software engineering (TypeScript / React / APIs / SDKs)
* Release engineering and production deploys
* Reliability, incident response, and customer engineering
* Quality engineering and test architecture
* CI/CD, developer tooling, and automation
* Performance and cost analysis
* Robotics edge-runtime / build-toolchain continuity
* AI-assisted engineering and coding-agent orchestration
* Engineering management and technical leadership

That breadth matters because most difficult software problems do not stay inside one of those boxes.

A production failure may start as a customer report, require log and database analysis, expose a code defect, need a regression test, uncover a weak CI gate, and eventually result in a release process change.

The skills in this repository try to capture that kind of end-to-end thinking.

At Formant (official title QA Manager), Brian's work expanded into hands-on engineering systems ownership: authoring and shipping production code, owning production releases and hotfixes, investigating and fixing production failures, building release/test/AI automation, and reviewing hundreds of changes from other engineers (1,000+ authored PRs; 400+ reviews).

Before that, Brian spent fourteen years at Articulate as the company grew from a small startup into a large software company, eventually working as an Engineering Manager.

These skills are an attempt to preserve the useful patterns from that experience in a form that AI agents can actually execute.

## The principles behind the skills

### Evidence over confidence

Do not say something works because the implementation looks reasonable.

Run it. Measure it. Inspect the output. Show the evidence.

### Test behavior, not just lines

A large test suite is not necessarily a strong test suite.

Good tests should prove important behavior, exercise edge cases, and fail when meaningful defects are introduced.

That is why Brian's testing approach combines:

* focused example tests
* property based testing
* mutation testing

Each answers a different question.

### Review the solution, not just the diff

Code review should ask more than:

> Does this code work?

It should also ask:

> Is this the right solution?

That means looking at blast radius, complexity, existing abstractions, downstream consumers, failure modes, tests, observability, rollback behavior, and whether a smaller solution exists.

### Production is part of the development loop

Shipping the code is not the end of the work.

Deployment behavior, logs, telemetry, customer reports, performance, regressions, and operational failures all provide information that should feed back into the implementation and the tests.

### Measure before optimizing

Performance and cost work should start with measurement.

Find the bottleneck. Establish the baseline. Change one thing. Measure again.

A plausible optimization is not the same thing as a demonstrated improvement.

### Make failure visible

A test that cannot fail CI is not a gate.

A monitor nobody sees is not useful.

A workflow that silently stops running is not automation you can trust.

Quality systems should make failures difficult to ignore and easy to investigate.

### Automate repeatable judgment

Brian is interested in automation that does more than execute commands.

The most useful systems capture a repeatable decision process:

* inspect a change
* gather evidence
* identify risk
* run the appropriate tests
* analyze failures
* communicate the result
* create the next artifact when appropriate

That philosophy led Brian from conventional automation into AI assisted test generation, automated test repair, visual analysis, PR review agents, and eventually reusable Agent Skills like these.

### AI is a force multiplier, not a substitute for engineering judgment

AI can generate enormous amounts of code very quickly.

That makes verification more important, not less important.

The useful question is not:

> Can an agent write this?

It is:

> Can the agent be given enough context, constraints, tools, verification, and feedback that the result can be trusted?

These skills are experiments in doing exactly that.

---

# Skills

| Skill                                  | What it teaches the agent                                                                                                                                                                                                  |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`pr-quality`](./pr-quality)           | Prepare and review pull requests using exact diff accounting, testing evidence, blast radius analysis, implementation review, and questions designed to challenge whether the proposed solution is actually the right one. |
| [`qa-unit-testing`](./qa-unit-testing) | Build stronger TypeScript unit tests by combining example based tests, fast-check property testing, and Stryker mutation analysis to find gaps ordinary coverage metrics miss.                                             |
| [`linkedin-vertical-captioned-clip`](./linkedin-vertical-captioned-clip) | Cut a live/stream recording into a LinkedIn 9:16 Remotion clip with TikTok-style one-word captions from Parakeet word timestamps (auto-editor), face-safe placement, filler stripping, and a short end fade. |

More skills will be added as Brian continues converting useful engineering practices into repeatable agent workflows.

## `pr-quality`

This skill comes from years of creating and reviewing production changes.

It pushes the agent beyond producing a polished PR description.

Among other things, it asks the agent to:

* calculate production versus test changes rather than guessing
* state exactly what testing was performed
* identify downstream consumers and blast radius
* examine whether the implementation fits existing architecture
* look for unnecessary complexity
* identify missing failure handling
* consider rollback and operational risk
* challenge whether the proposed implementation is the best solution

The goal is not a better looking pull request.

The goal is a better change.

## `qa-unit-testing`

Traditional unit tests tend to cover the examples the developer already thought about.

This skill layers three complementary techniques:

**Example tests** verify expected behavior for known cases.

**Property based tests with fast-check** explore combinations and edge cases the developer may never have considered.

**Mutation testing with Stryker** deliberately changes the implementation and asks whether the tests notice.

A test suite that executes every line but survives meaningful mutations still has gaps.

The goal is not maximum test count or maximum coverage.

The goal is tests that catch real defects.

---

## `linkedin-vertical-captioned-clip`

Turn a horizontal multi-cam live recording into a shareable LinkedIn vertical:

* Trim to the beat the user locks (absolute timestamps)
* Crop to the speaking stack (left cams → 1080×1920)
* Transcribe with **auto-editor + Parakeet `--split-words`** for real word times
* Render one-word TikTok-style captions in Remotion (not ffmpeg burn-in)
* Drop `uh`/`um` without retiming; fade out the last 0.5s

Do not evenly space transcript words — that is what made captions look unsynced.

---

# Installation

These skills follow the open [Agent Skills](https://agentskills.io) format and can be used by tools that support `SKILL.md`.

## Cursor

```bash
npx skills add elearningplugins/brians-agent-skills
```

Or copy an individual skill into:

```text
.cursor/skills/<skill-name>/
```

or:

```text
~/.cursor/skills/<skill-name>/
```

## Claude Code

```bash
npx skills add elearningplugins/brians-agent-skills -a claude-code
```

Or copy an individual skill into:

```text
.claude/skills/<skill-name>/
```

or:

```text
~/.claude/skills/<skill-name>/
```

## GitHub CLI

```bash
gh skill install elearningplugins/brians-agent-skills pr-quality
gh skill install elearningplugins/brians-agent-skills qa-unit-testing
gh skill install elearningplugins/brians-agent-skills linkedin-vertical-captioned-clip
```

## Manual installation

```bash
git clone https://github.com/elearningplugins/brians-agent-skills.git
```

Then point the agent at the appropriate skill directory.

---

# Examples

## Review a pull request

```text
/pr-quality

Review this PR. Verify the testing evidence, analyze its blast radius,
and challenge whether this is the right implementation rather than
only checking whether the code works.
```

## Prepare a pull request

```text
/pr-quality

Prepare a PR for the current branch using the pr-quality skill.
```

## Strengthen a test suite

```text
/qa-unit-testing

Review this module's tests. Add meaningful example tests, property based
coverage where appropriate, and use mutation testing to find assertions
that are missing.
```


## Make a LinkedIn vertical clip

```text
/linkedin-vertical-captioned-clip

Turn this horizontal multi-cam recording into a 9:16 LinkedIn clip with
one-word captions synced to the audio. Follow the skill in this repo.
```

---

# Why publish these?

For years, a lot of engineering knowledge lived in places like review comments, team conventions, scripts, checklists, debugging sessions, release processes, and things experienced engineers simply remembered to ask.

AI coding agents create an opportunity to make that knowledge executable.

A good Agent Skill can say:

> When you encounter this kind of problem, investigate it this way, gather this evidence, ask these questions, run these tools, and do not declare success until these conditions are true.

That is much more interesting than another collection of prompts.

This repository is where Brian is turning the engineering practices he wants an AI teammate to understand into reusable, inspectable, version controlled skills.

---

## Related

* [Brian Batt on GitHub](https://github.com/elearningplugins)
* [Brian's Job Search](https://briansjobsearch.com)
* [Agent Skills specification](https://agentskills.io)
* [Brian Batt on LinkedIn](https://www.linkedin.com/in/brianbatt/)

---

Created by **Brian Batt**.
