---
name: ast-tools-usage
description: Comprehensive workflow for using AST-Tools MCP server + semantic database codebase index. Covers all 80 tools, code-mode discovery, context injection, token budgeting, Hermes plugin integration, and best practices for structural code analysis.
category: software-development
version: 1.9.0
author: Lucien (RapidWebs Lead Digital Architect)
tags:
  - ast-tools
  - mcp
  - semantic-search
  - code-analysis
  - structural-editing
  - hermes-integration
  - code-mode
  - tool-discovery
triggers:
  - "ast tools"
  - "structural search"
  - "code analysis"
  - "semantic search"
  - "ast edit"
  - "ast fix"
  - "ast read"
  - "impact analysis"
  - "module imports"
  - "code mode"
  - "discovery mode"
---

# AST-Tools Usage Skill

**Purpose**: Master the complete AST-Tools workflow for structural code analysis, semantic search, and surgical Python editing. This skill covers all 11 MCP tools, the semantic database index, Hermes plugin integration, and proven patterns for real-world codebase tasks.

**Prerequisites**: 
- AST-Tools MCP server running (`ast-tools` in mcp_servers config)
- sqlite-vec extension installed
- Project indexed (`refresh_index` tool)

---

## Quick Reference: All 80 Tools

### Core AST (8)
| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `ast_grep` | Structural pattern search | `pattern`, `path`, `lang`, `limit` |
| `ast_read` | Extract API surface | `file`, `include_private`, `include_imports` |
| `ast_edit` | Surgical Python edits | `file`, `operation`, `params`, `dry_run` |
| `ast_generate_stub` | Generate .pyi stubs | `file`, `include_private`, `output_format` |
| `ast_refactor_extract_interface` | Extract ABC/Protocol | `file`, `class_name`, `interface_type` |
| `ast_capsule` | One-call symbol dossier | `symbol_name`, `file_path`, `include_callers` |
| `ast_query` | Smart router — describe intent | `intent`, `file`, `symbol`, `language` |
| `ts_edit` | TypeScript/TSX editing | `file`, `operation`, `params`, `lang` |

### Tool Discovery / Code-Mode (4)
| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `search_tools` | Search tools by natural language | `query`, `category`, `top_k` |
| `call_tool` | Execute a discovered tool | `name`, `arguments` |
| `tool_info` | Get full tool schema | `name`, `include_examples` |
| `tool_usage_stats` | Usage analytics dashboard | `top`, `sort_by` |

**Note**: When `discovery.mode=true` in config, only these 4 meta-tools are exposed to reduce context by ~96%. All 80 tools are still accessible via `search_tools` + `call_tool`.

---

## Code-Mode (Tool Discovery System)

**Code-mode** is the Cloudflare-inspired tool discovery pattern that reduces context token usage from ~20K (80 tools) to ~800 (4 meta-tools).

### How It Works

When enabled (`discovery.mode: true` in config), the server only exposes 4 meta-tools:

```
┌─────────────────────────────────────────────┐
│  Model Context (~800 tokens)                │
│                                             │
│  search_tools → call_tool → tool_info       │
│       ↘            ↙           ↓            │
│        Tool Discovery Layer                 │
│        (80 tools on server)                 │
└─────────────────────────────────────────────┘
```

### Usage Pattern

```python
# 1. Search for a tool by natural language
search_tools(query="structural search patterns", top_k=3)
# Returns: ast_grep, ast_query, structural_analysis

# 2. Get details about a specific tool
tool_info(name="ast_grep", include_examples=True)
# Returns: Full schema, parameters, examples

# 3. Call the tool with discovered parameters
call_tool(name="ast_grep", arguments={
    "pattern": "def $FUNC($$$ARGS)",
    "lang": "python",
    "limit": 10
})
```

### Enabling Code-Mode

**Config file** (`~/.config/rw-ast-tools/config.yaml`):
```yaml
discovery:
  mode: true  # Enable code-mode
```

**Environment variable**:
```bash
export AST_TOOLS_DISCOVERY_MODE=true
```

**Default**: `false` (all 80 tools exposed for backward compatibility)

### Benefits

- **96% context reduction**: ~20K tokens → ~800 tokens
- **Better LLM accuracy**: Avoids tool schema overload (benchmarks show >50 tools = <30% accuracy)
- **Dynamic discovery**: Tools can be added without regenerating context
- **Usage analytics**: `tool_usage_stats` tracks call counts, error rates, latency

### Accessing All Tools

Even in code-mode, all 80 tools remain accessible:
- `search_tools` can find any tool by description
- `call_tool` can execute any tool by name
- `tool_info` can retrieve full schema for any tool
- `tool_usage_stats` provides analytics across all tools

---

## Semantic Search + Context Injection (Phase 8B)

### The Workflow (Automatic with Hermes Plugins)

```python
# 1. Search by MEANING (not keywords)
results = semantic_search(
    query="authentication middleware handler",  # Natural language
    k=10,
    inject_context=True,        # DEFAULT: True
    token_budget=4096,          # Token budget for context
    diversity_limit=3           # Max symbols per file
)

# 2. Response includes BOTH results AND formatted context
{
    "results": [...symbol objects...],
    "context_injection": {
        "context_markdown": "# Context\n\n## file.py:10\nclass AuthHandler:\n    ...",  # Ready for LLM
        "tokens_used": 1234,
        "budget_remaining": 2862,
        "diversity_applied": true
    }
}
```

### When to Use Each Search Tool

| Task | Tool |
|------|------|
| "Find code by what it does" | `semantic_search` (vector + FTS5 hybrid) |
| "Find code by exact pattern" | `ast_grep` (AST pattern matching) |
| "Search symbol names only" | `search_symbols` (FTS5) |
| "Find definition by qualified name" | `find_symbol_definition` |

---

## Mandatory Pre-Work Checklist

**Before ANY code modification:**

```bash
# 1. Orient to project
codebase_summary(cwd=".")                    # <500 token architecture overview
project_info(cwd=".", full=true)             # Full project manifest

# 2. Read target file structure
ast_read(file="path/to/target.py", include_private=true)

# 3. Map impact (MANDATORY for public API changes)
impact_analysis(target="path/to/target.py")  # What breaks?

# 4. Check imports (MANDATORY for module splits)
module_imports(module="target_module")       # Fan-in/fan-out
```

---

## Common Workflow Patterns

### Pattern 1: Understand Before Edit

```python
# Step 1: Read the file
ast_read(file="src/auth/middleware.py", include_private=true)

# Step 2: NEW — Use ast_query if unsure which tools to use
ast_query(intent="find all callers and understand impact", file="src/auth/middleware.py")
# → Recommends: find_references + impact_analysis with pre-filled params

# Step 3: Check what calls it
find_references(symbol="AuthMiddleware", cwd=".")

# Step 4: Impact analysis (MANDATORY for public API changes)
impact_analysis(target="src/auth/middleware.py")

# Step 5: NEW — Get complete symbol dossier in one call
ast_capsule(symbol_name="AuthMiddleware", file_path="src/auth/middleware.py")
# → Returns: definition + signature + docs + imports + refs + callers + callees + impact

# Step 6: Edit surgically
ast_edit(
    file="src/auth/middleware.py",
    operation="replace_node",
    params={"target": "class AuthMiddleware:", "replacement": "class AuthMiddlewareV2:"},
    dry_run=true  # ALWAYS FIRST
)
```

### Pattern 2: Refactor Large Module → Subpackage

```python
# 1. Map ALL imports TO/FROM target
structural_analysis(analysis_type="dependencies", file="src/large_module.py")

# 2. Check for circular deps
module_imports(module="large_module")

# 3. Create subpackage structure
# mkdir -p src/large_module/subpkg/
# Create __init__.py with __all__ exports

# 4. Extract each responsibility to submodule
# 5. Run tests AFTER EACH extraction
# 6. Create compat shim (old file = `from .subpkg import *`)
```

### Pattern 3: Semantic Search for Unknown Codebase

```python
# "Where is the database connection pool?"
semantic_search(query="database connection pool", k=5, inject_context=true)

# "How does error retry logic work?"
semantic_search(query="error retry logic exponential backoff", k=10, inject_context=true)

# "Find authentication handlers"
semantic_search(query="authentication handler middleware", kind="class", k=10, inject_context=true)
```

### Pattern 4: Token Budget Management

```python
# For small context window models
semantic_search(query="...", token_budget=2048, diversity_limit=2)

# For large context window models  
semantic_search(query="...", token_budget=8192, diversity_limit=5)

# Disable context injection if you only need raw results
semantic_search(query="...", inject_context=false)
```

---

## Hermes Plugin Integration (Phase 8B)

### ⚠️ CRITICAL: Plugin Limitations vs Tool Capabilities

**Important distinction:** The Hermes plugins (`ast-tools-context`, `ast-tools-tokens`) are **NOT the same** as the `semantic_search` tool's context injection feature.

| Feature | Hermes Plugins | `semantic_search` tool |
|---------|---------------|------------------------|
| **What it injects** | Static ~1000-token capability docs | Dynamic project-specific symbols |
| **Trigger** | AST keywords in user query | Explicit tool call |
| **Project-aware** | ❌ No — same docs for every project | ✅ Yes — returns YOUR code |
| **Relevance scoring** | ❌ None | ✅ 6-factor (semantic, recency, usage, kind, proximity, callgraph) |
| **Token budget** | ❌ None | ✅ Enforced via `token_budget` param |

**Current plugin behavior:**
```python
# User: "Where is the websocket handler in my project?"
# Plugin returns: Generic docs about what ast_grep does
# This is NOT helpful — you need actual code locations
```

**Correct approach — use `semantic_search` directly:**
```python
# User: "Where is the websocket handler in my project?"
semantic_search(
    query="websocket handler",
    k=5,
    inject_context=True,      # Returns YOUR actual symbols
    token_budget=4096,
    diversity_limit=3
)
# Returns: src/nexusagent/server/server.py:75 (actual code)
```

### Plugin Improvement Opportunities (Partially Implemented - 2026-07-30)

**Dynamic minimal tool schemas now implemented** — The `ast-tools-context` plugin now generates tool documentation dynamically from the actual registered tools instead of hardcoded docs. This means:

1. **Dynamic tool schemas** — `generate_quick_reference()` builds a markdown table from `TOOL_SCHEMAS` registry
2. **"Did you mean?" corrections** — `find_similar_tool()` uses difflib to catch mistyped tool names
3. **Always up-to-date** — When new tools are added with schemas, they auto-appear in injected context

```python
# User: "How do I use ast_greg?"
# Plugin detects misspelling, injects:
# "⚠️ Did you mean `ast_grep`? (you typed `ast_greg`)"
```

**Remaining gap — Project-aware semantic injection:**
```python
# Future improvement: plugin calls semantic_search with user's query
# This would inject actual project symbols, not just tool docs
def inject_ast_tools_context(user_message: str, **kwargs):
    if ast_keyword_detected(user_message):
        # Instead of returning static docs, call:
        results = semantic_search(query=user_message, k=5, inject_context=True)
        return {"context": results["context_injection"]["context_markdown"]}
```

**Effort:** 2-3 hours to refactor. This would make plugins project-aware and actually useful.

### Current Plugin Behavior (What Actually Happens)

When you ask about AST/code structure topics, the `ast_tools_context` plugin **automatically injects** generic documentation:

```
User: "How do I use ast_grep to find all async functions?"
→ pre_llm_call hook fires
→ Plugin detects AST keywords
→ Injects static ~1000-token capability overview
→ You get generic docs, NOT your project's actual code
```

For **project-specific context**, always call `semantic_search` with `inject_context=True` directly.

### Verified Working: Both Context Injection Layers (2026-07-30)

| Layer | What It Injects | Trigger |
|-------|-----------------|---------|
| **Hermes Plugin** (`ast-tools-context`) | Static ~1000-token capability docs | AST keywords in user query |
| **MCP Tool** (`semantic_search`) | **Dynamic project-specific symbols** — signatures, docstrings, file paths, relevance scores | Explicit tool call with `inject_context=true` (default) |

**Test results (108 tests passing):**
- Plugin auto-injection: 3084 chars injected on AST keyword query ✅
- Token budget tracking: Warning at 2500 tokens (budget 1000) ✅
- Context pressure warning: Fires at 95.4% usage (80% of compression threshold) ✅
- Semantic search context injection: 5 results, 904 tokens used, 1096 remaining, diversity applied ✅

---

## Tool-Specific Patterns

### code_validate_syntax — Multi-Language Validation ✨ NEW (Phase 10A)

**Purpose**: Validate code syntax without executing it. Returns validation errors with line/column positions.

**Supported Languages**:
- **Compiler-based**: Python (`ast`), SQL (`sqlparse`), Shell (`bash -n`), JavaScript (`node --check`), TypeScript (`tsc --noEmit`), Rust (`rustc`), Go (`go build`)
- **Tree-sitter**: C, C++, C# (syntax-only, no type checking)

```python
# Python validation
result = code_validate_syntax({"content": "def foo(): return 1", "language": "python"})
# Returns: {"valid": True, "errors": [], "warnings": [], "parser_used": "ast.parse", "duration_ms": 0.5}

# Invalid Python
result = code_validate_syntax({"content": "def foo( return 1", "language": "python"})
# Returns: {"valid": False, "errors": [{"line": 1, "column": 8, "message": "invalid syntax", "error_type": "syntax"}], ...}

# C++ validation (tree-sitter)
result = code_validate_syntax({"content": "int main() { return 0; }", "language": "cpp"})
# Returns: {"valid": True, "errors": [], "parser_used": "tree-sitter (tree-sitter-cpp)"}

# C# validation
result = code_validate_syntax({"content": "class Program { static void Main() {} }", "language": "c#"})

# Graceful degradation when compiler not installed
result = code_validate_syntax({"content": "package main", "language": "go"})
# If go not found: {"valid": False, "errors": [{"message": "go not found"}], "parser_used": "none"}
```

**Security Design**:
- ✅ Uses **stdin pipes** (not temp files with user code) for subprocess calls
- ✅ Workspace validation for file paths (prevents path traversal)
- ✅ `errors='replace'` for unicode handling
- ✅ Finally blocks for cleanup
- ✅ `@mcp_tool` decorator (not `@lcp_tool`)

**When to Use**:
- Before writing code to a file (validate generated code)
- During code review (catch syntax errors early)
- When generating code snippets (ensure they're valid)
- Multi-language projects (consistent validation interface)

**Test Coverage**: 62 tests passing (>90% coverage target)

### ast_grep — Structural Search

```python
# Find all function definitions
ast_grep(pattern="def $FUNC($$$ARGS)", lang="python")

# Find specific method calls
ast_grep(pattern="call($OBJ, $METHOD)", lang="python")

# Find class definitions with decorators
ast_grep(pattern="class $NAME($$$BASES):", lang="python")

# Cross-language: find all test functions
ast_grep(pattern="def test_$NAME($$$ARGS)", lang="python", path="tests/")
```

### ast_edit — Surgical Python Edits

```python
# Rename function (preserves all call sites via libcst)
ast_edit(
    file="src/utils.py",
    operation="rename_function",
    params={"old_name": "old_func", "new_name": "new_func"},
    dry_run=true
)

# Add parameter with default
ast_edit(
    file="src/api.py",
    operation="add_parameter",
    params={"function": "handle_request", "param_name": "timeout", "default_value": "30"},
    dry_run=true
)

# Replace entire node (class, function, block)
ast_edit(
    file="src/models.py",
    operation="replace_node",
    params={"target": "class User:", "replacement": "class User(BaseModel):"},
    dry_run=true
)
```

### structural_analysis — Code Intelligence

```python
# Who calls this function?
structural_analysis(analysis_type="callers", symbol="process_payment", file="src/payments.py")

# What does this function call?
structural_analysis(analysis_type="callees", symbol="process_payment", file="src/payments.py")

# Class inheritance hierarchy
structural_analysis(analysis_type="type_hierarchy", symbol="BaseHandler", file="src/handlers.py")

# All references to symbol
structural_analysis(analysis_type="references", symbol="Config", file="src/config.py")

# Module dependency graph
structural_analysis(analysis_type="dependencies", project_root=".")
```

### impact_analysis — Change Risk Assessment

```python
# Before ANY public API change
impact_analysis(target="src/api/public_endpoint.py")

# Returns:
# - Direct dependents (files importing from target)
# - Transitive dependents (call chain)
# - Test files that may break
# - Risk assessment (low/medium/high/critical)
```

### find_references — Symbol Usage

```python
# Before renaming ANY symbol
find_references(symbol="UserService", cwd=".")

# Returns: file, line, context for each usage
```

### module_imports — Import Analysis

```python
# Before splitting a module
module_imports(module="src/services/user_service", cwd=".")

# Returns:
# - fan_in: what imports FROM this module (with line numbers)
# - fan_out: what this module imports
# - circular dependencies detected
# - import lines with file/line context
```

### ts_edit — TypeScript/TSX Structural Editing ✨ NEW (Phase 3A, 2026-06-29)

**Purpose**: Surgical code editing for TypeScript, TSX, JavaScript, and JSX using tree-sitter AST transformations.

**Supported Languages**: `typescript`, `tsx`, `javascript`, `jsx`

**Operations**:
| Operation | Parameters | Description |
|-----------|------------|-------------|
| `rename_identifier` | `old_name`, `new_name` | Rename variable, function, class, interface |
| `add_parameter` | `function`, `param_name`, `default_value?` | Add parameter to function signature |
| `replace_node` | `query` (tree-sitter query), `replacement` | Replace any node matched by query |

**Usage**:
```python
# Rename a React component
result = ts_edit(
    file="src/components/Button.tsx",
    operation="rename_identifier",
    params={"old_name": "OldButton", "new_name": "Button"},
    lang="tsx",
    dry_run=True
)

# Add parameter to function
result = ts_edit(
    file="src/utils/api.ts",
    operation="add_parameter",
    params={"function": "fetchData", "param_name": "timeout", "default_value": "5000"},
    lang="typescript",
    dry_run=True
)

# Replace with tree-sitter query
result = ts_edit(
    file="src/component.tsx",
    operation="replace_node",
    params={"query": "(jsx_element) @element", "replacement": "<NewComponent />"},
    lang="tsx",
    dry_run=True
)
```

**Validation**: Every edit re-parses the modified code — returns error if result doesn't parse.

**MCP Tool**: `ts_edit(file, operation, params, lang, dry_run)`

**Limitations** (vs Python's `ast_edit` with libcst):
- String-based transformation (not CST) — may lose some formatting
- No comment preservation guarantee
- Basic parameter handling (no type annotation inference)
- Best effort on complex JSX

---

### dead_code_enhanced — Dead Code with 6 False Positive Reductions ✨ NEW (Phase 1, 2026-06-29)

**Purpose**: Find unused code with **>40% → <20% false positive rate** via 6 reduction strategies.

**Usage**:
```python
# Basic usage
result = dead_code_enhanced(project_root=".", entry_points=["main.py", "cli.py"])

# Auto-detects entry points if not provided
result = dead_code_enhanced(project_root=".")
```

**Returns**:
```json
{
  "dead_functions": [
    {
      "name": "unused_helper",
      "file": "utils.py:42",
      "confidence": "high",  // high | medium | low
      "reason": "No references or alive signals detected",
      "alive_signals": [],
      "symbol_type": "function"
    }
  ],
  "dead_classes": [...],
  "dead_methods": [...],
  "summary": {
    "total_dead_functions": 15,
    "total_dead_classes": 3,
    "total_dead_methods": 8,
    "false_positive_mitigations": {
      "framework_decorators": 12,  // Excluded via Flask/FastAPI/etc decorators
      "exported_symbols": 5,       // Excluded via __all__
      "entry_point_symbols": 20,   // Reachable from entry points
      "scc_cluster_members": 4,    // Mutually recursive (Tarjan SCC)
      "interface_implementations": 6  // Implements interface methods
    }
  }
}
```

**6 False Positive Reduction Strategies**:

1. **Polymorphism Tracking** - Marks interface/protocol implementations as alive
   - Detects `@abstractmethod` and override patterns
   - Uses `ImplementsDetector` to track implementations
   
2. **Framework Decorator Detection** - 20+ decorators across 6 frameworks:
   - **Flask**: `@route`, `@app.route`, `@blueprint.route`
   - **FastAPI**: `@get`, `@post`, `@put`, `@delete`, `@patch`
   - **Celery**: `@task`, `@shared_task`
   - **Click**: `@command`, `@group`
   - **Django**: `@admin.register`, `@receiver`
   - **Pytest**: `@fixture`

3. **Entry Point Analysis** - Traces call graph from entry points:
   - Auto-detects: `main.py`, `__main__.py`, `cli.py`, `app.py`, `wsgi.py`, `asgi.py`, `manage.py`, `celery.py`
   - Marks reachable symbols as low-confidence

4. **SCC Cluster Detection** - Tarjan's algorithm for circular dead code:
   - Identifies mutually recursive functions (e.g., `even()` ↔ `odd()`)
   - Marks cluster members as potentially alive

5. **`__all__` Exports Check** - Respects explicit module exports:
   - Exported symbols get medium confidence (not high)
   - Acknowledges intentional public API

6. **Confidence Scoring** - Per-finding confidence with reasoning:
   - **High**: No references or alive signals
   - **Medium**: Some signals (`__all__`, abstract methods)
   - **Low**: Strong signals (decorators, entry points, implementations)

**Example Workflow**:
```python
# Find HIGH confidence dead code only (least likely false positives)
result = dead_code_enhanced(".")
high_conf_dead = [f for f in result["dead_functions"] if f["confidence"] == "high"]

# Check what was excluded
mitigations = result["summary"]["false_positive_mitigations"]
print(f"Excluded via entry points: {mitigations['entry_point_symbols']}")
print(f"Excluded via decorators: {mitigations['framework_decorators']}")

# Filter to show only truly unused code
truly_dead = [
    f for f in result["dead_functions"]
    if f["confidence"] == "high" and len(f.get("alive_signals", [])) == 0
]
```

**Test Coverage**: 7 tests in `tests/test_enhanced_dead_code.py`  \n**Implementation**: `src/ast_tools/tools/enhanced_dead_code.py` (524 lines)  \n**Documentation**: `docs/ENHANCED_DEAD_CODE.md`

**⚠️ Known Limitation**: Full-project analysis can **timeout** on large codebases (>100 files) when run via CLI (`ast find-dead`). For large projects, run via Python script with extended timeout, or analyze subdirectories individually:
```bash
# Analyze specific subdirectory only
python3 -c "
from ast_tools.tools.enhanced_dead_code import find_dead_code_enhanced
result = find_dead_code_enhanced('src/ast_tools/tools/', None)
print(f'Found: {len(result.get(\"dead_functions\", []))} dead functions')
"
```

---

## Index Management

### Incremental Indexing — Already Implemented

**Your question:** "Does the semantic database get rebuilt if a file changes? Can it reindex one file?"

**Answer:** ✅ **Yes — both ways:**

```python
# 1. Manual per-file reindex (via watcher daemon)
reindex_path(file_path="/path/to/file.py")

# 2. Manual project reindex (incremental via content hashing)
refresh_index(project_path=".", force=False)  # Only changed files

# 3. Automatic watching (starts watcher daemon)
watch_add(paths=["./src"])  # Watches for changes, 100ms debounce
```

**How `refresh_index` incremental works:**
```python
# Lines 144-170 in refresh_index.py
content_hash = compute_file_hash(file_path)  # SHA256
cached_hash = get_cached_hash(conn, rel_path)
if cached_hash == content_hash:
    # SKIP — file unchanged
    continue
# Only reindex changed files
```

**Watcher daemon (`daemon.py`):**
- Uses `watchdog` for cross-platform file events
- Debounces 100ms (prevents multiple index on IDE save)
- Queue-based with thread-safe locking

**⚠️ Gap:** The watcher is **not auto-started** on server launch.

**Fix needed:** Add `watch_add(path=".")` to server `__main__.py` startup sequence (1-line change).

```python
# Examples
refresh_index(path=".", force=true)   # Full rebuild
refresh_index(path=".")               # Incremental (hash-based)
index_status()                        # symbols, files, embeddings count
```

---

## Wave 2 Core Infrastructure — Persistent SQLite Pool with Fallback (2026-06-28 NexusAgent)

**Context:** Implementing persistent aiosqlite connection pool with graceful fallback to thread pool when aiosqlite unavailable (externally-managed-environment).

### Pattern: Persistent Connection Pool with Fallback

```python
# Import with graceful degradation
try:
    import aiosqlite
    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False
    logger.warning("aiosqlite not available — using thread pool fallback for async operations")

class HybridMemoryIndex:
    def __init__(self, workspace_dir: str):
        # ... init ...
        self._db_pool = None  # Persistent aiosqlite connection
        self._init_db()

    @asynccontextmanager
    async def _get_connection(self):
        """Get or create persistent aiosqlite connection (if available)."""
        if not AIOSQLITE_AVAILABLE:
            # Fallback: signal sync methods via executor
            yield None
            return

        if self._db_pool is None:
            self._db_pool = await aiosqlite.connect(...)
            # configure pool...
        yield self._db_pool

    async def close(self):
        if self._db_pool is not None:
            await self._db_pool.close()
            self._db_pool = None
```

### Search with Graceful Fallback

```python
async def search(self, query: str, max_results: int = 6, min_score: float = 0.1) -> list[dict]:
    query_vec = await self.embedder.embed(query)
    candidate_limit = max_results * CANDIDATE_MULTIPLIER
    
    if not AIOSQLITE_AVAILABLE:
        # Run sync methods in executor
        loop = asyncio.get_running_loop()
        keyword_future = loop.run_in_executor(None, self._search_keyword_sync, query, candidate_limit)
        vector_future = loop.run_in_executor(None, self._search_vector_sync, query_vec, candidate_limit)
        keyword_results = await keyword_future
        vector_results = await vector_future
    else:
        keyword_results, vector_results = await asyncio.gather(
            self._search_keyword(query, candidate_limit),
            self._search_vector(query_vec, candidate_limit),
        )
    # merge results...
```

### Sync Fallback Methods

```python
def _search_keyword_sync(self, query: str, limit: int) -> list[dict]:
    conn = sqlite3.connect(str(self.db_path))
    try:
        # FTS5 query via run_in_executor
        return [{"id": r[0], "file": r[1], "content": r[2], "rank": r[3]} for r in rows]
    finally:
        conn.close()

def _search_vector_sync(self, query_vec: list[float], limit: int) -> list[dict]:
    conn = sqlite3.connect(str(self.db_path))
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        # sqlite-vec KNN query
        return results
    finally:
        conn.close()
```

### Results

- **When aiosqlite available:** Persistent connection, native async, no thread pool overhead
- **When aiosqlite unavailable:** Thread pool fallback, sync methods in executor, graceful degradation
- **Zero code duplication** — sync methods used by both fallback and direct sync calls
- **Tested:** Works in externally-managed-environment (Debian 13) where aiosqlite unavailable

**Result:** Wave 2 complete — Persistent SQLite pool with thread pool fallback working.

### DO ✅
- Use `ast_read` before any edit
- Use `impact_analysis` before public API changes
- Use `module_imports` before module splits
- Run `dry_run=true` first on `ast_edit`
- Use `semantic_search` with `inject_context=true` for LLM-ready context
- Let Hermes plugins auto-inject docs on AST queries

### DON'T ❌
- Use grep/rg for code patterns → use `ast_grep`
- Use sed/awk/patch for Python → use `ast_edit`
- Skip impact analysis on public APIs
- Batch multiple edits without testing between
- Assume `ast_edit` works without `dry_run` verification

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "no such module: vec0" | Install sqlite-vec: `uv pip install sqlite-vec` |
| Migration fails | Check `load_vec_extension(conn)` called before init_schema |
| Rollback doesn't work | Delete schema_version row: `DELETE FROM schema_version WHERE version = 5` |
| Context too large | Reduce `token_budget`, increase `diversity_limit` |
| Plugin not firing | Enable with `hermes plugins enable ast-tools-context` |
| **MCP server fails to start: `ModuleNotFoundError`** | **Two common causes:**<br>**(1) Wrong Python interpreter**: MCP config uses system Python but ast-tools needs venv. Fix: Edit `~/.hermes/config.yaml` → change `ast-tools.command` from `/usr/bin/python3` to `/home/sysop/Workspaces/ast-tools/.venv/bin/python3` (or `.venv/bin/python`), then `systemctl --user restart hermes-gateway`.<br>**(2) Import bug in semantic_search.py**: `from src.ast_tools.context` should be `from ..context`. Fix: `patch(path="src/ast_tools/tools/semantic_search.py", old_string="from src.ast_tools", new_string="from ..")`.<br>**Diagnostic flow:** Check logs (`tail ~/.hermes/logs/mcp-stderr.log`) → identify error → fix config or code → restart → verify. See `references/mcp-server-troubleshooting.md`. |
| **Path traversal validation breaks tests** | **When adding path traversal security checks, handle missing `project_path` gracefully:**<br>**(1) Check for `None` before validation**: `if project_path and not file_path.is_relative_to(project_path):` not `if not file_path.is_relative_to(project_path):`<br>**(2) Parse safely**: `project_path = Path(args.get("project_path")).resolve() if args.get("project_path") else None`<br>**(3) Tests must declare fixtures**: Adding `project_path` param? Test function signature must include `(self, test_project)`<br>**(4) Update ALL test calls**: Use script to add `project_path` to all `_tool_ast_read` and `_tool_ast_edit` calls, not just obvious ones<br>**Pattern:** Security checks should skip when `project_path` not provided (legacy code, tests), not crash. See `references/secure-validation-pattern.md`. |

---

## Quick Verification Commands

```bash
# Test all tools work
hermes mcp call ast-tools ast_grep '{"pattern": "def $FUNC", "lang": "python"}' --limit 1

# Test semantic search with context
hermes mcp call ast-tools semantic_search '{"query": "test", "inject_context": true, "k": 1}'

# Verify plugins loaded
hermes plugins list | grep ast-tools
```

### Python API Verification (for programmatic use)

```python
# All tools accept dict args, not keyword args
from src.ast_tools.tools.semantic_search import _tool_semantic_search
from src.ast_tools.tools.ast_grep import _tool_ast_grep
from src.ast_tools.tools.refresh_index import _tool_refresh_index

# semantic_search
result = await _tool_semantic_search({
    "query": "websocket handler",
    "k": 5,
    "inject_context": True,
    "token_budget": 4096,
    "diversity_limit": 3,
    "lang": "python"
})

# ast_grep (returns dict, not awaitable)
result = _tool_ast_grep({
    "pattern": "async def session_websocket",
    "path": "/path/to/src",
    "lang": "python",
    "limit": 10
})

# refresh_index (returns dict)
result = await _tool_refresh_index({
    "project_path": "/path/to/project",
    "force": True,
    "embeddings": True
})
```

---

## Verification Results (2026-07-24)

| Test | Status | Notes |
|------|--------|-------|
| Semantic search + context injection | ✅ Pass | Returns `context_injection` with markdown, tokens_used, budget_remaining, diversity_applied |
| ast_grep structural search | ✅ Pass | Found `session_websocket` handler at `src/nexusagent/server/server.py:75` |
| refresh_index (203 Python files) | ✅ Pass | Embeddings generated with all-MiniLM-L6-v2 (384 dim) |
| Token budget enforcement | ✅ Pass | 477/4096 tokens used in test |
| Diversity limiting | ✅ Pass | Max 3 symbols per file enforced |
| FTS5 special chars | ⚠️ Note | `@` char causes syntax error — escape or avoid in queries |

## Verification Results (2026-07-30) — Hermes Plugin Integration Test

| Component | Test | Result | Details |
|-----------|------|--------|---------|
| `ast-tools-context` plugin | Enabled in config, loads at startup | ✅ Pass | `pre_llm_call` hook registered, injects ~1000-token capability docs on AST keywords |
| `ast-tools-tokens` plugin | Enabled in config, loads at startup | ✅ Pass | `pre_llm_call` + `post_tool_call` hooks registered |
| Token budget tracking | Large result on `mcp_ast_tools_ast_grep` | ✅ Pass | 2500 tokens → warning logged: "exceeded budget: budget 1000" |
| Context pressure warning | 250k tokens in 262k window | ✅ Pass | Warning injected at 95.4% usage (80% of compression threshold) |
| Context injection trigger | Query "How do I use ast_grep..." | ✅ Pass | 3084 chars injected, detects AST keywords correctly |
| Semantic search context injection | Query "context injection" | ✅ Pass | 5 results, 904 tokens used, 1096 remaining, diversity applied |
| Test suite (context/ + tools/) | 108 tests | ✅ Pass | All passing in 11.83s |

### Key Finding: Plugin Limitation vs Tool Capability

**The Hermes plugins inject GENERIC docs, NOT project-specific code.** This is a design limitation, not a bug.

| Scenario | What Happens | What You Need |
|----------|--------------|---------------|
| User: "Where is the websocket handler?" | Plugin injects generic `ast_grep` docs | Call `semantic_search(query="websocket handler", inject_context=True)` |
| User: "How do I use ast_edit?" | Plugin injects generic `ast_edit` docs | ✅ Plugin IS helpful here — generic usage docs |

**Rule**: For project-specific code locations → use `semantic_search` directly. For how-to questions about tools → plugins work fine.

---

## Integration with Other Skills

| Skill | When to Combine |
|-------|-----------------|
| `nexus-code-review` | Code review with structural analysis |
| `refactoring-extract-to-subpackage` | Module extraction workflow |
| `systematic-debugging` | Debug with impact analysis |
| `writing-plans` | Plan refactoring with codebase_summary |
| `subagent-driven-development` | Parallel analysis tasks |

---

## Version History

- **1.9.0** (2026-08-02): **Code-Mode Implementation + Documentation Update** —
  - **Code-mode config support**: Added `discovery.mode` to server config with proper priority (config > env var > default)
  - **Daemon mode fix**: Fixed hardcoded `tools/list` handler to use decorated `handle_list_tools()` which respects discovery mode
  - **Documentation**: Updated skill to reflect 80 tools (was 12 in quick ref), added code-mode section explaining the Cloudflare-inspired tool discovery pattern
  - **Context optimization**: Code-mode reduces context from ~20K tokens to ~800 tokens (96% reduction)
  - **Config location**: `~/.config/rw-ast-tools/config.yaml` with `discovery.mode: true` to enable

- **1.8.0** (2026-07-31): **Dynamic Tool Schemas + "Did You Mean?" + Project Context Plugin** — 
  - **Dynamic minimal tool schemas**: `src/ast_tools/tools/dynamic_schemas.py` generates compact markdown reference table (~400 tokens) for all 43 tools from registered schemas. No more hardcoded docs in Hermes plugin.
  - **"Did you mean?" correction**: `find_similar_tool()` in `__init__.py` uses difflib to suggest correct tool names when user types partial/misspelled names (e.g., `ast_greg` → `ast_grep`, `sematic_search` → `semantic_search`).
  - **Project semantic context plugin**: New `ast_tools_project_context` plugin calls `semantic_search` with user's query to inject ACTUAL project code (signatures, docstrings, file paths) instead of generic tool docs. Saved as reference in `references/ast_tools_project_context_plugin.py` + `.yaml`.
  - All 43 tools now have schemas registered in `__init__.py` for dynamic generation.
  - LSP tools (7) and context tools and context tools (2) now have schemas too.
  - Updated `generate_quick_reference()` produces complete markdown table with descriptions + required params.

- **1.7.0** (2026-06-30): **Phase 8 Incremental Indexing (Symbol-Level Diff)** — New diff engine (`src/ast_tools/indexer/diff.py`, 183 lines) classifies symbols as added/removed/modified/unchanged using `(file_path, qualified_name)` match key. Database helpers: `get_symbols_by_file`, `delete_symbol_cascade`, `update_symbol_fields`. `refresh_index` now defaults to incremental mode (only update changed symbols). Preserves IDs, edges, and embeddings for unchanged symbols. 30 new tests (20 diff + 10 incremental). Added `references/phase8-incremental-indexing.md`. Pitfall captured: `database_context` does NOT auto-commit — must call `conn.commit()` explicitly.

- **1.3.0** (2026-06-29): **Phase 1 Enhanced Dead Code Detection** — Implemented 6 false-positive reduction strategies (>40% → <20% FP rate): (1) Polymorphism tracking via ImplementsDetector, (2) Framework decorator detection (20+ decorators across 6 frameworks), (3) Entry point analysis with call graph tracing, (4) Tarjan's SCC algorithm for circular dead code, (5) __all__ exports check, (6) Confidence scoring (High/Medium/Low with alive_signals). New tool: `dead_code_enhanced`. Test suite: 7 tests, all passing. Total: 409/409 tests pass. Documentation: `docs/ENHANCED_DEAD_CODE.md` + `references/phase1-enhanced-dead-code.md`.

- **1.5.0** (2026-06-29): **Phase 3A TypeScript Structural Editing + Full CLI Completion** — 
  - **TypeScript/TSX Structural Editing** (`ts_edit` tool): tree-sitter based editing for TypeScript, TSX, JavaScript, JSX. Operations: `rename_identifier`, `add_parameter`, `replace_node`. Validation via re-parsing. TSX/JSX grammar support added to `ts_backend.py` with React-specific patterns (`jsx_element`, `jsx_self_closing`, `component`).
  - **CLI Phase 2 Complete**: All 11 commands now operational with semantic database access. New commands: `callers`, `callees`, `deps`, `browse`. Direct callers/callees via `_ast_find_*`, import analysis via `module_imports`, symbol browsing via `list_symbols`. 3 output formats (table/JSON/markdown). Comprehensive test suite (`tests/test_cli.py`).
  - **Documentation**: `docs/CLI_REFERENCE.md` (15KB complete guide), `docs/AST_TOOLS_QUICKSTART.md` (13KB intro), `docs/USAGE_RULES.md` (6KB "don't modify" guide).
  - Tool count: 42 (including `ts_edit`, `ast_query`, `ast_capsule`, `dead_code_enhanced`).

---

## AST-Tools CLI — Terminal Workflows ✨ NEW (Phase 2, 2026-06-29)

**Purpose**: Access AST-Tools capabilities from the terminal, shell scripts, and CI/CD pipelines — no MCP required.

**Installation**:
```bash
cd ~/Workspaces/ast-tools
source .venv/bin/activate
pip install -e .  # Registers 'ast-tools' entry point
```

**Usage**:
```bash
# All commands support: --project-root (-p), --format (-f), --help (-h)
ast <command> [options]

# Output formats: table (default), json, markdown
```

### 11 Commands

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Semantic search (hybrid FTS5 + vector) | `ast search "auth handler"` |
| `navigate` | Jump to symbol definition | `ast navigate SessionManager` |
| `blast-radius` | Impact analysis | `ast blast-radius src/auth.py:42` |
| `find-dead` | Enhanced dead code (6 FP reductions) | `ast find-dead --format json` |
| `summary` | Codebase overview | `ast summary --format markdown` |
| `symbols` | List symbols in file | `ast symbols src/auth.py` |
| `refs` | Find all references | `ast refs authenticate` |
| `callers` | Who calls this symbol | `ast callers process_payment` |
| `callees` | What does this symbol call | `ast callees main --file-path src/main.py` |
| `deps` | Import fan-in/fan-out | `ast deps src/api/handlers.py` |
| `browse` | Browse all symbols with filters | `ast browse --kind function -n 20` |

### Workflow: Command-Line Code Review

```bash
# 1. Get project overview
ast summary --format markdown

# 2. Find potentially dead code
ast find-dead --format json | jq '.dead_functions[] | select(.confidence == "high")'

# 3. Verify it's truly unused
ast callers unused_function  # Should return "No callers found"

# 4. Check import dependencies
ast deps src/module.py

# 5. Find all references before refactoring
ast refs OldClassName
```

### Workflow: CI/CD Integration

```bash
#!/bin/bash
# CI check: Fail if high-confidence dead code exists
ast find-dead --format json 2>/dev/null | \
  jq -e '.dead_functions[] | select(.confidence == "high")' && \
  echo "❌ Dead code found" && exit 1 || \
  echo "✅ No high-confidence dead code" && exit 0
```

### Workflow: Shell Scripting

```bash
# Browse all functions in project
ast browse --kind function --format json | \
  jq -r '.symbols[] | "\(.file):\(.line) \(.name)"'

# Find callers and export to file
ast callers main_function --format json > callers.json

# Summary for metadata extraction
ast summary --format json | jq '.languages.python.files'
```

### Important Notes

- **Async handling**: CLI uses `asyncio.run()` internally for `semantic_search` — this is transparent to users
- **Index required**: `search` command requires indexed database (`refresh_index` tool first)
- **Entry points**: `find-dead` auto-detects entry points, or specify with `--entry-points "main.py,cli.py"`
- **Performance**: Most commands complete in <2s for 100-file projects

**Documentation**: See `docs/CLI_REFERENCE.md` for complete command reference, examples, and scripting patterns.

- **1.2.0** (2026-06-28): **Medium-depth audit completed** — Full inline audit (subagent timeouts on >30 file projects). Found 1 HIGH (path traversal in 5 tools), 4 MEDIUM (test dep gap, test assertion drift, watcher coverage, oversized files), 3 LOW (lint, module state, secret_sanitizer coverage). Added `references/audit-medium-20260628.md` with full findings and prioritized action plan.
- **1.1.0** (2026-07-26): **UX Improvements Adopted from code-intel-plugin** — Five major enhancements inspired by competitor analysis:\\n  - **ast_read**: Graceful Unicode handling with fallback summary (no more crashes on box-drawing chars)\\n  - **semantic_search**: Auto-refresh empty indexes + actionable hints (self-healing)\\n  - **ast_grep**: Context-aware pattern syntax hints in error messages (teaches $VAR, $$$ARGS)\\n  - **ast_query** (NEW): Smart router — natural language → best tool recommendation (saves memorizing 41 tool names)\\n  - **ast_capsule** (NEW): Consolidated symbol dossier in one call (replaces 4-5 separate tool calls)\\n  Tool count: 39 → 41. Commit: `4439468` "feat: Add smart router and consolidated view". Multi-machine sync: both workstation + server updated.\\n- **1.0.7** (2026-06-27): **Multi-machine deployment with uv venv pattern** — Critical fixes for PEP 668 (externally-managed-environment) on Debian 12+:\\n  - **Use `uv` instead of pip**: `uv venv` creates venv with pip, `uv pip install` bypasses PEP 668 restrictions\\n  - **Disk space handling**: When `/` partition full (76%), venv creation fails. Check `df -h /` and `df -h /home` — use separate partitions with 100+ GB. Set `PIP_CACHE_DIR=/home/user/.cache/pip` and `HOME=/home/user` during install.\\n  - **Minimal dependencies**: Base ast-tools needs only `mcp`, `libcst`, `tree-sitter`, `sqlite-vec`. Heavy deps (`sentence-transformers`, `torch`, `cuda-bindings`) only for curator/dependency/index tools. Install in stages: `uv pip install -e .` first, then `uv pip install sentence-transformers`.\\n  - **Multi-machine sync workflow**: (1) Fix workstation with uv → (2) Test tool count (`from ast_tools.tools import TOOL_REGISTRY`) → (3) rsync to server: `rsync -avz --delete src/ast_tools/tools/ user@server:/path/` → (4) SSH verify: `ssh user@server ".venv/bin/python -c 'from ast_tools.tools import TOOL_REGISTRY; print(len(TOOL_REGISTRY))'"`.\\n  - **Server verification**: 39 tools = all deps present. 17-18 tools = missing heavy deps. 11 tools = only core tools loading.\\n  See `references/uv-venv-mcp-fix.md` for full troubleshooting transcript.
- **1.0.1** (2026-07-24): Added verification results and Python API patterns. See `references/verification-2026-07-24.md` for detailed test transcripts.
- **1.0.2** (2026-07-25): **Added `code_validate_syntax` tool (Phase 10A)** — 10-language syntax validation (Python, SQL, Shell, JS, TS, Rust, Go via compilers; C, C++, C# via tree-sitter). 62 tests passing. Security: stdin pipes, workspace validation, unicode handling.
- **1.0.3** (2026-07-26): **Clarified Hermes plugin limitations** — plugins inject static docs, NOT project-specific code. For actual project symbols, use `semantic_search(inject_context=True)` directly. Added incremental indexing documentation (SHA256 content hashing, watcher daemon with 100ms debounce). Noted watcher auto-start gap (1-line fix needed in server `__main__.py`).
- **1.0.4** (2026-07-26): **P0 Plugin Enhancements Implemented** — Three new plugin capabilities:\n  - `ast-tools-context`: Added `on_session_start` hook with compact ~200-token tool index + verification reminder\n  - `ast-tools-tokens`: Added `post_tool_call` error correction hook (ast_edit, semantic_search, ast_grep, impact_analysis)\n  - `verification-gate`: New cross-project quality gate plugin (enforces verification-before-completion on every session)\n  See `references/plugin-enhancements-p0.md` for full implementation details and test scenarios.\n- **1.0.7** (2026-06-27): **Multi-machine deployment with uv venv pattern** — Critical fixes for PEP 668 (externally-managed-environment) on Debian 12+:\\n  - **Use `uv` instead of pip**: `uv venv` creates venv with pip, `uv pip install` bypasses PEP 668 restrictions\\n  - **Disk space handling**: When `/` partition full (76%), venv creation fails. Check `df -h /` and `df -h /home` — use separate partitions with 100+ GB. Set `PIP_CACHE_DIR=/home/user/.cache/pip` and `HOME=/home/user` during install.\\n  - **Minimal dependencies**: Base ast-tools needs only `mcp`, `libcst`, `tree-sitter`, `sqlite-vec`. Heavy deps (`sentence-transformers`, `torch`, `cuda-bindings`) only for curator/dependency/index tools. Install in stages: `uv pip install -e .` first, then `uv pip install sentence-transformers`.\\n  - **Multi-machine sync workflow**: (1) Fix workstation with uv → (2) Test tool count (`from ast_tools.tools import TOOL_REGISTRY`) → (3) rsync to server: `rsync -avz --delete src/ast_tools/tools/ user@server:/path/` → (4) SSH verify: `ssh user@server ".venv/bin/python -c 'from ast_tools.tools import TOOL_REGISTRY; print(len(TOOL_REGISTRY))'"`.\\n  - **Server verification**: 39 tools = all deps present. 17-18 tools = missing heavy deps. 11 tools = only core tools loading.\\n  See `references/uv-venv-mcp-fix.md` for full troubleshooting transcript.\\n- **1.0.6** (2026-06-27): **Added MCP server troubleshooting pattern** — diagnostic workflow for `ModuleNotFoundError` when MCP server uses system Python instead of venv. Steps: check logs → verify config → test manually → fix config → restart gateway → verify. Added `references/mcp-server-troubleshooting.md` with full workflow.
## References

- `references/virtualenv-exclusion-fix.md` — **NEW (2026-07-30)**: Virtual environment exclusion fix for all project scanners
- `references/phase8-incremental-indexing.md` — **NEW (2026-06-30)**: Symbol-level diff engine, database ops, test pitfalls
- `references/phase3-code-quality-audit.md` — **NEW (2026-06-29)**: Systematic code quality audit workflow — dead code analysis, ruff auto-fix, manual security verification, prioritized fix lists, example commit messages, time estimates
- `references/phase3a-typescript-editing.md` — TypeScript/TSX structural editing with tree-sitter
- `references/documentation-cleanup-workflow.md` — **NEW (2026-06-30)**: Systematic doc cleanup — archive obsolete, consolidate by topic, remove cache artifacts, maintain lean docs/ structure
- `references/server-capability-verification.md` — Quick-start server deployment commands
- `references/cli-development-pattern.md` — CLI development workflow
- `references/mcp-server-troubleshooting.md` — **NEW (2026-06-27)**: Diagnostic workflow for MCP server startup failures
- `references/multi-machine-deployment.md` — **NEW (2026-06-27)**: Multi-machine deployment pattern
- `references/audit-medium-20260628.md` — **NEW (2026-06-28)**: Medium-depth audit results
- `references/secure-validation-pattern.md` — **NEW (2026-06-28)**: Path traversal security fix pattern — graceful degradation, test update workflow, pytest fixture discipline