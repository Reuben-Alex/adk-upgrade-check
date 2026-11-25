# Contributing

Thanks for helping. The most valuable contribution is a new rule for a `google-adk` change that
breaks real code.

## Setup

```bash
git clone https://github.com/Reuben-Alex/adk-upgrade-check
cd adk-upgrade-check
uv sync
uv run pytest
```

## Adding a rule

1. **Confirm the break against the tagged source.** The changelog wording is a lead, and the tagged
   source is the ground truth. Find the commit that made the change, and reproduce the break on the
   releases either side of it, for example:

   ```bash
   uv run --no-project --with google-adk==2.13.0 python tests/ground_truth/enum_args.py
   uv run --no-project --with google-adk==2.14.0 python tests/ground_truth/enum_args.py
   ```

   Add or extend a script in `tests/ground_truth/`. If the break doesn't reproduce, don't ship the
   rule.

2. **Write the rule** in `src/adk_upgrade_check/rules/adk<major><minor>_<slug>.py`:

   - `id`: `ADK<major><minor>-SLUG`, for example `ADK214-ENUM-ARGS`. It is stable forever.
   - `introduced_in`: the first release with the change.
   - `severity`: `error` (fails or silently misbehaves), `warning` (behaviour changed and may
     matter) or `info` (worth knowing).
   - `changelog_url`: the exact upstream commit.
   - The module docstring: a short explanation, which `explain <RULE_ID>` prints.
   - `check(project)`: yields findings. Use `self.finding(...)` for Python code and
     `self.text_finding(...)` for other files. Mark a finding `confidence="likely"` when static
     analysis can't be sure.
   - A fix (optional): pass `replacement=` only when the rewrite keeps the old behaviour exactly.

   Then register it in `rules/__init__.py`.

3. **Add fixtures** in `tests/fixtures/<RULE_ID>/`:

   - `positive/`: code that breaks. End each line that must be reported with `# expect`.
   - `negative/`: look-alike code that must not be reported. This is where the false-positive
     budget is enforced.
   - `fixed/`: for fixable rules, exactly what `--fix` should produce from `positive/`.

   A case is one `.py` file, or a directory holding a small project (for rules that also read
   `pyproject.toml`, requirements or dashboards).

4. **Run it on real code.** Run the rule on a few public ADK projects, and label what it reports.
   Precision matters more than recall: if you aren't sure about a pattern, leave it out or mark it
   `likely`.

## Style

The code follows ADK's own style (2-space indents, one import per line), to keep upstreaming easy.
Keep changes small and focused.
