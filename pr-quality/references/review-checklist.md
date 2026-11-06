# PR Review Checklist

## Evidence

- Is the problem/root cause verified rather than guessed?
- Does the PR distinguish production LOC from tests/config?
- Are test claims tied to actual commands/results?
- Are performance claims backed by measurements?
- Does verification exercise the real runtime path?

## Seven review questions

1. Behavior-changing or additive?
2. Performance impact, with real data?
3. What could still be wrong or missing?
4. What incidental/bundled changes are easy to miss?
5. iPhone Safari or equivalent constrained-runtime compatibility?
6. Adjacent behavior sharing the same surface/state/path?
7. Shared-package/service downstream blast radius?

For shared consumers, classify propagation as **inert**, **purely additive**, or **behavior-changing**.

## Staff-level solution review

### Symptom vs. disease
Is this fixing the root class or one instance? Is that scope deliberate?

### Detect vs. prevent
Can the design make drift/impossible state impossible rather than testing for it after the fact?

### Time bombs
What cap, pin, compatibility assumption, migration, or workaround will expire?

### CI / efficiency
Is verification redundant, fragile, missing, or incapable of failing the build? Is an expensive check being applied too broadly?

### Under-justified judgment
Why this version floor, timeout, retry count, concurrency limit, threshold, cache duration, or compatibility cutoff?

### Right solution
Is the approach effective, efficient, maintainable, and performant, not merely correct?

## PR body

Are all acronyms other than `PR` listed in a final `## Acronyms` section rather than expanded inline?

## Review-writing style

Lead with findings that can change the decision to merge. Prefer a concrete failure mode, why it matters, evidence, and the smallest credible correction. Keep comment replies short and human.
