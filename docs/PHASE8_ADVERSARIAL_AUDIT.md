# Phase 8 — Adversarial Audit (Security + Edge Cases)

**Project:** rw-promptforge
**Date:** 2026-08-04

---

## Attack Surface

### 🔴 CRITICAL: Shell injection via `--eval-command`

**File:** `src/rw_promptforge/evaluator/shell.py:26-31`

```python
command = self.command_template.replace("{path}", artifact_path)
result = subprocess.run(command, shell=True, ...)
```

**Attack vector:** If `artifact_path` contains shell metacharacters (`;`, `|`, `` ` ``, `$()`), the substituted command executes arbitrary code.

**Severity:** CRITICAL — remote code execution if path originates from user input.

**Fix:** Use `shlex.quote(artifact_path)` before substitution:

```python
import shlex
safe_path = shlex.quote(artifact_path)
command = self.command_template.replace("{path}", safe_path)
```

**Or better**: pass as list `cmd = ["sh", "-c", command]` with proper escaping.

---

### 🔴 CRITICAL: API key in reflection prompt to external LLM

**Location:** `src/rw_promptforge/evaluator/shell.py:81-93`

`EvalResult.format_trace()` includes STDOUT and STDERR from the eval command. If an eval command outputs API keys, tokens, paths, or credentials, that text is sent to the reflection LLM — possibly a third-party provider.

**Severity:** CRITICAL — data exfiltration risk.

**Fix:** Add `--sanitize-eval-output` flag. Default: scrub lines matching env-like patterns (`KEY=`, `token:`, `Bearer`) from evaluation traces.

---

### 🟠 HIGH: No input validation on file paths

**Location:** `src/rw_promptforge/cli.py:19`

```python
@click.argument("path", type=click.Path(exists=True))
```

`click.Path(exists=True)` only checks existence — not path safety.

**Edge case:** Symlinks pointing outside workspace, files in `/proc`, `/sys`, `/dev`. These are technically "existing paths" but shouldn't be eval'd.

**Fix:** Add `resolve_path=True` (resolves symlinks) + check if resolved path is under `rr`.

---

### 🟠 HIGH: Tempfile race condition

**Location:** Not yet implemented (would be in optimizer.py)

Write-to-tempfile-then-evaluate creates a window where another process could modify or replace the temp file before the eval runs.

**Severity:** Medium (we own the temp dir). Still TOCTOU risk.

**Fix:** Write to a temp directory with restrictive permissions (0700), use `tempfile.mkstemp()` with delete=False, and verify content after write.

---

### 🟠 MEDIUM: Provider API key in process environment

**Location:** `src/rw_promptforge/provider.py:70-74`

API keys are `os.environ.get()` — visible to any subprocess.

**Mitigation:** Document. This is standard practice for CLI tools. Do not log or print keys.

---

### 🟡 MEDIUM: Large artifact → unbounded tokens

**Location:** `src/rw_promptforge/reflector/engine.py:77`

The reflection prompt sends the ENTIRE artifact text to the LLM with no truncation. A 100KB SOUL.md would produce a prompt exceeding most model context windows → silent failure or 4xx error.

**Fix:** Add `max_artifact_chars=60000` truncation with head+tail preservation.

---

### 🟡 MEDIUM: No rate limiting on reflection calls

**Location:** `src/rw_promptforge/reflector/engine.py:77`

The loop calls reflect() up to `max_rounds` times (default boring 3). Provider handles rate limits — but if user sets `--max-rounds 1000` they could hammer the API.

**Fix:** Cap max_rounds at 20.

---

### 🟡 LOW: Provider `from_env` silently uses empty key

**File:** `provider.py:70`

`os.environ.get("OPENAI_API_KEY")` can be `""` (empty or missing). The provider initializes with empty key and sends `Authorization: Bearer ` header — certain endpoints reject empty auth.

**Fix:** Raise `ValueError` if no key provided and endpoint requires one (openai/goog etc.)

---

## Edge Cases

| Case | Result | Status |
|------|--------|--------|
| Artifact file is binary (not text) | `Path.read_text()` raises `UnicodeDecodeError` | ⚠️ Unhandled |
| Artifact is 0 bytes | Reflector receives empty string, LLM may hallucinate | ⚠️ Unhandled |
| Reflection LLM returns junk/empty text | Becomes "improved" artifact; loop breaks silently | ⚠️ Unhandled |
| Reflection LLM returns original unchanged | Loop spins until max_rounds → stops | ✅ Handled (stops) |
| Shell command hangs forever | `timeout=300` kills it; returns EvalResult(err) | ✅ Handled |
| Shell command dumps 10MB stderr | `.strip()` called but all text goes into EvalResult → then to LLM → context overflow | ⚠️ Sound-potential OOM |
| skill YAML has no frontmatter | `.split("---", 2)` → entire content becomes `_body` | ✅ Handled |
| skill YAML frontmatter is malformed | `yaml.safe_load()` → `None`, treated as empty dict | ⚠️ Unhandled (silently ignores bad YAML) |

---

## Summary

| Severity | Count | Priority Fix |
|----------|-------|-------------|
| 🔴 Critical | 2 | Shell injection, API key leak |
| 🟠 High | 2 | Path validation, tempfile race |
| 🟡 Medium | 4 | Truncation, ratelimit, empty key, large output |

**Total edge cases found:** 10 (6 code + 4 behavioral)