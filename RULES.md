# Contributing Rules — DataSpoc Pipe

Rules for maintaining the project vision. Use this to evaluate PRs.

---

## 1. Scope Rules

**Pipe does ONE thing: move data from source to bucket as Parquet.**

| ACCEPT | REJECT |
|--------|--------|
| New Singer tap template | DAG/orchestration features |
| Bug fix in Parquet conversion | Data transformation/dbt features |
| New cloud provider (e.g., MinIO) | Query/analysis features (that's Lens) |
| Better error messages | Web UI or dashboard |
| Performance improvement in streaming | Streaming/real-time ingestion |
| New built-in tap | ML features |
| Incremental extraction improvement | Multi-tenancy/RBAC |

**The golden question:** "Does this help move data from A to B?" If no, reject.

---

## 2. Architecture Rules

### Bucket Convention is Sacred

The directory structure in the bucket is a **public contract**. DataSpoc Lens and external tools depend on it.

```
<bucket>/.dataspoc/manifest.json
<bucket>/raw/<source>/<table>/dt=YYYY-MM-DD/<file>.parquet
```

- **Never change the structure without a version bump in manifest**
- **Never rename paths** — add new paths, deprecate old ones
- Any change here requires approval from Lens maintainers

### Never Implement Auth — IAM Handles It

DataSpoc does not implement authentication, authorization, or RBAC. Cloud provider IAM (AWS IAM, GCP IAM, Azure AD) controls who can access which buckets. Pipe needs WRITE access to the destination bucket — that's it. Any PR that adds user management, access control lists, or permission checks must be rejected. Best practice is separate buckets per permission level.

### Stateless Design

- All shared state lives in the bucket (manifest, state, logs)
- No local database, no daemon, no server
- A user can delete `~/.dataspoc-pipe/` and only lose local config, not data

### Singer Protocol

- Taps are external subprocesses — never import tap code as library
- Parse stdout line-by-line (SCHEMA, RECORD, STATE)
- Always `nan_to_num` before writing Parquet
- Never modify tap output — convert types but don't transform data

---

## 3. Code Rules

### Must Have
- Every new feature needs tests (`pytest`)
- Every CLI command needs `--help` text
- Error messages must be actionable ("Install with: ..." not just "ModuleNotFoundError")
- Config validated with Pydantic before use
- Cloud operations use fsspec abstraction (never raw boto3/gcloud)

### Must NOT Have
- No hardcoded cloud credentials in code
- No `print()` for user output — use `console.print()` (Rich)
- No blocking operations without timeout
- No silent `except: pass` — at minimum log the error
- No Python < 3.10 syntax

### Style
- CLI messages in English
- Function/variable names in English, snake_case
- Docstrings for public functions
- Type hints on function signatures
- Keep files under 300 lines — split if bigger

---

## 4. PR Checklist

Before approving any PR:

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] No new dependencies without justification
- [ ] Error messages are user-friendly
- [ ] Bucket convention not modified
- [ ] No secrets in code
- [ ] CLI help text present for new commands
- [ ] Works with `file://` (local) and `s3://` (cloud)

---

## 5. Dependency Rules

- **Core deps** (typer, pydantic, pyarrow, fsspec, pyyaml, rich): update freely
- **Cloud backends** (s3fs, gcsfs, adlfs): always optional extras, never in core
- **New deps**: must justify. Prefer stdlib or existing deps over new ones
- **Singer taps**: external packages, not our responsibility. Built-in taps are exceptions

---

## 6. Release Rules

- Semantic versioning: `MAJOR.MINOR.PATCH`
- Breaking changes to bucket convention: MAJOR bump
- New features: MINOR bump
- Bug fixes: PATCH bump
- Every release needs changelog entry
- Test on `file://` (local) and at least one cloud provider before release
