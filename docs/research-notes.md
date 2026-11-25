# Research notes (2026-11-25)

What I checked before building the prototype, and what changed in the design as a result.

## Corrections to the design doc

| Design doc said | Actually | Source |
|---|---|---|
| Python 3.10 or later, "matching ADK's floor" | ADK 2.15.1 requires Python **3.11** or later (`requires-python = ">=3.11"`), so the tool does too, and it can use `tomllib`. | `pyproject.toml` at v2.15.1 |
| `ADK200-ASYNC-DB-URL`: sync URLs break in 2.0 | They break in **1.19.0**, where `DatabaseSessionService` switched to `create_async_engine`. The changelog listed it under features ("Full async implementation of DatabaseSessionService"), not breaking changes. Renamed `ADK119-ASYNC-DB-URL`. | `database_session_service.py` at v1.18.0 vs v1.19.0; ground truth in `tests/ground_truth/async_db_url.py` |
| `sqlite:///` URLs are fine | They fail too: only `sqlite+aiosqlite://` works. This is the most common real-world case (all 9 corpus findings). `postgresql+psycopg://` (psycopg 3) is fine, because it has an async mode. | ground truth; `_ASYNC_DRIVER_BY_BACKEND` in v2.15.1 |
| Latest release 2.15.0 | 2.15.1 (2026-11-24): bug fixes only, no new breaking changes. | PyPI, CHANGELOG |
| ADK214-ENUM-ARGS needed for all Enums | `(str, Enum)` members still compare, hash and `json.dumps` as strings; only `str()` and f-strings change. `IntEnum` and `StrEnum` are unaffected. Plain `Enum` and `Flag` break everything string-like. | 2.14.0 changelog wording; ground truth `tests/ground_truth/enum_args.py` |
| Every 2.x minor has breaking changes | Confirmed sections in 2.6.0, 2.7.0, 2.13.0, 2.14.0 and 2.15.0. 2.14.0 also lists *behavior changes* (for example `json` columns for new session tables). | CHANGELOG |

Verified as stated: google/adk-python#4387 (Alembic RFC, open), #4408 (Alembic PR, open, last updated 2026-09-16), #3343 (open). The downstream examples exist: zazza123/chatomon#118, shoom1/agentic-cli#200 ("support google-adk 2.13 beside 2.12"), doughayden/agent-foundation#363.

## Prior art

- No upgrade checker or codemod for `google-adk` exists (web search; GitHub issue search on adk-python for "upgrade check", "codemod", "breaking changes migration tool": no results).
- doughayden/agent-foundation#363 is the manual version of this tool. The maintainer writes that they checked by hand that the template "has no enum-typed tool arguments, and it runs no SQL of its own against the session tables", and tells forks to review the release notes themselves.

## How google/adk-python takes contributions (CONTRIBUTING.md)

- A Google CLA is required.
- **For large changes, open an issue first.** Outline the proposal and design, and discuss before writing the PR.
- PRs should be small and focused, include a testing plan, and link an issue.
- ADK is developed internally and mirrored to GitHub with Copybara. An accepted PR often shows as *closed* (not merged), labelled `merged`, with the change landing as a separate commit.
- User-facing changes also need a PR to google/adk-docs.
- google/adk-python-community is the **official community repo** (published as `google-adk-community` on PyPI, 188 stars). It is for tools, integrations and plugins outside the core, governed by module owners (the original contributors). It is a possible home, though it is organised as a library rather than a CLI.

## Upstream strategy

1. Keep it a standalone package (the `bump-pydantic` model: a separate tool, linked from the official migration docs).
2. Open a design issue on google/adk-python with the demo, ground truth and corpus numbers. Ask whether the maintainers would link it from adk.dev's upgrade notes, or host it in adk-python-community, and whether they'd take a thin `adk upgrade check` hook. Draft: `docs/upstream-issue-draft.md`.
3. Smaller upstream PRs that help either way: machine-readable breaking-change metadata per release, or `DeprecationWarning`s that name a replacement.

## Verified while building the rules

| Claim | Result | Evidence |
|---|---|---|
| 2.0 docs: overridden `_run_async_impl` / `generate_content` are "bypassed by the graph engine" | **Not reproduced.** On the `Runner` path, overrides on both `BaseAgent` and `LlmAgent` subclasses still run in 1.39.1, 2.0.0 and 2.15.1. No rule shipped, because it would flag working code. The docs may describe agents run as nodes inside a `Workflow`. This could be an upstream docs issue. | `tests/ground_truth/run_override.py` |
| 2.0 docs: don't call `enqueue_event` directly | No `def enqueue_event` exists in ADK 2.15.1. The only corpus hit was A2A's `EventQueue.enqueue_event`, so the rule only checks `session.events.append`. | grep of v2.15.1; corpus |
| 2.0 docs: `except BaseException` traps `NodeInterruptedError` | True, but it is raised only from `ctx.run_node()`, a 2.x feature that 1.x code can't use. So it isn't an upgrade break, and there is no rule. | `workflow/_errors.py`, `_dynamic_node_scheduler.py` |
| 2.6: file artifacts namespaced by app | Old `root/users` artifacts are still read, but the first save restarts version numbering and hides older versions. It's an info rule, not an error. | commit f72f0db |
| 2.7: pyarrow left `gcp` | `google-adk[gcp]==2.6.3` imports the plugin and pyarrow. On 2.7.0 it raises `ImportError`. `[all]` still includes pyarrow. | `tests/ground_truth/removals.py` |
| 2.13: `call_llm` span removed | Real, but code often handles both schemas (adk-samples' `trace_converter.py` checks `call_llm` *or* `gen_ai.*`), so findings are `likely`. | corpus |
| 2.14: Vertex `create_session` kwargs | 2.13.0 merged extra kwargs into the config (`config.update(kwargs)`). On 2.14.0, `session_state=` raises `ValueError`. Renaming to `state=` / `session_id=` keeps the behaviour. | `tests/ground_truth/removals.py` |
| 2.15: builder removed | `google.adk.cli.built_in_agents` imports on 2.14.1 and raises `ModuleNotFoundError` on 2.15.0. | `tests/ground_truth/removals.py` |
| 1.19: CLI `--session_service_uri sqlite://` | The CLI registry maps `sqlite` to the new `SqliteSessionService` (1.18 used `DatabaseSessionService` for `sqlite`, `postgresql` and `mysql`). A database written by 1.18 makes 1.19.0 and 2.15.1 raise `RuntimeError: … seems to use an old schema`. It is not in the changelog's breaking changes. New rule: `ADK119-SQLITE-SERVICE`. | `tests/ground_truth/sqlite_cli_switch.py` |
| 1.19: CLI `postgresql+asyncpg://` | Unregistered schemes fall back to `DatabaseSessionService` (1.19 `fast_api.py`; later `service_factory.py`), so rewriting a CLI `postgresql://` to `+asyncpg` is safe. | source at v1.19.0, v2.0.0 |
| 2.14: Enum args for bound methods | `FunctionTool(Billing().get_price)` converts too (2.13: `str`, 2.14: `Plan`), so methods registered as tools are followed. | `tests/ground_truth/enum_args.py` |

## Rule ideas found during research (not built yet)

- 2.14.0 behavior change: `DatabaseSessionService` uses `json` columns for new tables (affects custom SQL against session tables).
- 2.15.0: `DYNAMIC_INSTRUCTION_ROUTING` is on by default (`load_artifacts` and `load_mcp_resource` instructions move out of `system_instruction`).
- Monkey-patches of private ADK functions (agent-foundation patches `_setup_telemetry`). A general "private API you touch changed between versions" rule could diff the two tagged sources.
