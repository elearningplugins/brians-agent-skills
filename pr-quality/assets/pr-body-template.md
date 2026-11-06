# Portable PR Body Template

> Reconstructed portable template based on recovered PR requirements and filled-out PR examples. It is not claimed to be the literal historical organization template.

## Summary

<!-- What changed? Keep this concrete. -->

## Why

<!-- Problem, verified root cause, intended behavior, and important non-goals. -->

## Tickets / issues

<!-- Follow repository convention. Legacy DEV example:
Fixes [DEV-12345] — Exact ticket title
-->

## Lines of code

| Category | File | + | − |
|---|---|---:|---:|
| Fix | `path/to/file` | 0 | 0 |
| **Fix subtotal** | | **0** | **0** |
| Fix (config) | `path/to/config` | 0 | 0 |
| **Fix (config) subtotal** | | **0** | **0** |
| Tests | `path/to/test` | 0 | 0 |
| **Tests subtotal** | | **0** | **0** |
| **Total** | | **0** | **0** |

Net production change: **+0 lines**.

## Testing

### Automated tests

- Command:
- Result:
- Suites/tests:
- Runtime:

### Coverage

- Measured:
- Result:

### Property-based tests

- Properties/invariants:
- Counterexamples discovered:
- Deterministic regression added:

### Mutation testing

- Scope:
- Result:
- Survivors:
- Equivalent/tooling survivors:
- Local/on-demand or CI-gated:

### Integration / browser / device / manual verification

- Verified:
- Not verified:

### Performance evidence

- Before:
- After:
- Conditions:
- Interpretation:

## Review questions

### 1. Does this fix/feature change existing behavior, or is it additive?

### 2. What is the performance impact — positive or negative?

### 3. What bugs or issues could we be missing here?

### 4. What else was fixed/implemented here that may not be obvious or properly documented?

### 5. Will this functionality/fix work on iPhone Safari or the comparable constrained supported runtime?

### 6. Does this alter any existing, adjacent behavior sharing the same component, event surface, API, state, persistence layer, or execution path?

### 7. If this ships in a shared package/library/service, what is the downstream blast radius?

| Consumer | Uses touched surface? | Effect | Verification |
|---|---|---|---|
| | | Inert / additive / behavior-changing | |

## Known limitations / follow-ups

<!-- Time bombs, deliberately deferred root-class fixes, rollout coordination, or unverified areas. -->

## Acronyms

<!-- Keep this section last. List every acronym used above, or delete the section if there are none. Do not expand acronyms inline. -->

- **ABC** - What the acronym stands for
