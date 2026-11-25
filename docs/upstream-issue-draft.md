<!-- Draft for a google/adk-python issue (feature request). Not posted. -->

# Proposal: a static "will this upgrade break me?" check for google-adk

## Problem

Several minor releases since 2.0 have had breaking or behavior changes (2.6.0, 2.7.0, 2.13.0, 2.14.0 and 2.15.0), and some breaks were not labelled as breaking. For example, the 1.19.0 async rewrite of `DatabaseSessionService` makes every `sqlite:///` and `postgresql://` URL fail at startup. So each team audits each release by hand:

- doughayden/agent-foundation#363 checked by hand that the template "has no enum-typed tool arguments, and runs no SQL of its own against the session tables", and told forks to review the notes themselves.
- zazza123/chatomon#118 and shoom1/agentic-cli#200 carry compatibility work for 2.13.
- #4387 describes users being afraid to update because of database changes.

## What I built

`adk-upgrade-check` (Apache-2.0): https://github.com/Reuben-Alex/adk-upgrade-check. It parses a project with LibCST (it never imports or runs it), detects the current `google-adk` from lock files, and reports, for each release between `--from` and `--to`, the exact lines that break. Mechanical cases are fixed with `--fix`, which shows the diff first.

```
$ adk-upgrade-check . --to 2.15.1
google-adk 1.18.0 (from uv.lock)  ->  target 2.15.1   (11 rules apply)

ERROR   ADK119-ASYNC-DB-URL       billing/agent.py:17
        DatabaseSessionService URL uses the synchronous scheme `sqlite://`. Since 1.19.0 ...
        fix: use `sqlite+aiosqlite://` ...   [auto-fixable]

ERROR   ADK214-ENUM-ARGS          billing/tools.py:10
        `plan == "pro"` compares Enum tool argument `plan` with a string. From 2.14.0 FunctionTool passes Plan members, so this is always False.
        fix: compare against `Plan.PRO`   [auto-fixable]
```

**Evidence so far:**
- It has 11 rules, covering 1.19 through 2.15. Six of them are reproduced on the real releases either side of the change: 1.18.0 vs 1.19.0 (twice), 2.6.3 vs 2.7.0, 2.13.0 vs 2.14.0 (twice) and 2.14.1 vs 2.15.0. One of them, the CLI `sqlite://` session-service switch in 1.19, is not in the changelog's breaking changes at all.
- On 22 public ADK projects plus adk-samples, `ADK119-ASYNC-DB-URL` found 9 real breaks in 7 repos, with no false positives. Two of those repos are pinned to exactly 1.18.0.
- Findings are split into `certain` and `likely`; only `certain` fails CI by default.

## Questions for maintainers

1. Would you **link to it** from the upgrade notes on adk.dev (the way Pydantic's migration guide links `bump-pydantic`), or **host it** in adk-python-community?
2. Would you accept a **thin `adk upgrade check` command** that runs the tool if it's installed (as an optional extra) and prints install instructions if not? I'd keep it to a few lines and no new core dependencies.
3. Is there appetite for **machine-readable breaking-change metadata** per release (for example a small YAML file next to CHANGELOG.md), so rules can be drafted as each release is cut?

Separately: the 2.0 notes say overridden `_run_async_impl` methods are bypassed, but on the `Runner` path they still run in 2.0.0 and 2.15.1 (repro script linked). Should the docs say this applies only to agents run as workflow nodes?

I'm happy to do the work for any of these.

<!-- Before posting: sign the Google CLA at https://cla.developers.google.com/ -->

