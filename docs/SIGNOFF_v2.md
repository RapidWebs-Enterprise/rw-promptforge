# rw-promptforge v2 — Sign-Off Document

**Date:** 2026-08-04  
**Mode:** LOW  
**Status:** READY FOR IMPLEMENTATION  

---

## Plan Status: ✅ APPROVED

All phases complete:

| Phase | Status | Output |
|-------|--------|--------|
| 0. Research | ✅ | 7 papers, 2 research docs |
| 1. Spec | ✅ | `SPECMERGED_v2.md` (628 lines) |
| 2. Plan | ✅ | `PHASE2_PLAN_v2.md` (242 lines) |
| 3. Forward Audit | ✅ PASS | 18/18 claims verified |
| 4. Reverse Audit | ⚠️ FAIL→PATCHED | 6 math errors fixed |
| 5. Synthesis | ✅ | `PHASE5_SYNTHESIS_v2.md` (9.1KB) |

---

## Critical Fixes Applied (from Reverse Audit)

1. **Inverted fix_rate logic** — Low fix rate now correctly signals convergence
2. **Hamming distance → SequenceMatcher** — Works on variable-length strings
3. **Cosine similarity → Jaccard token similarity** — No embedding model needed
4. **Size stability uses `len(artifact)`** — Not `len(change_summary)`
5. **Per-round cap → Total cap** — Prevents exponential 1.5^20× growth
6. **Artifact hash stored in history** — Enables stagnation detection

---

## Implementation: 12 Steps, ~6 Hours

```
Step 1:  Core data structures + utilities (45m)
Step 2:  Categories module — 4-scoring (45m)
Step 3:  Convergence module — fixed math (45m)
Step 4:  Auditor module — reverse audit (45m)
Step 5:  Refactor optimizer loop (60m)
Step 6:  SessionDB trace API (20m)
Step 7:  Reflector size budget (15m)
Step 8:  Evaluator output cap (10m)
Step 9:  ARMORED section parsing (30m)
Step 10: Tests (60m)
Step 11: Integration test (20m)
Step 12: CLI wiring (15m)
```

**Files:** 13 created/modified, ~1050 lines

---

## Verification Baseline

- Existing tests: **18/18 passing** ✅
- All spec claims verified against source code ✅
- Convergence math audited and fixed ✅

---

## Approve to begin implementation?

**Yes** — Start coding Steps 1-12 immediately

**No** — Wait for modifications
