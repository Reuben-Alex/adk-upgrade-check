"""Parses a project once and answers "what does this name refer to?".

The analysis is static: user code is parsed with LibCST, never imported.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import libcst as cst
from libcst.metadata import CodeRange
from libcst.metadata import MetadataWrapper
from libcst.metadata import PositionProvider

SKIP_DIRS = {
    ".git", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__",
    "build", "dist", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    "site-packages",
}  # fmt: skip

# Non-Python files some rules read: dependency specs, env files (`.env`,
# `.env.example`, ...), deploy scripts, dashboards and Agent Config YAML.
TEXT_FILES = (
    ".toml", ".txt", ".cfg", ".ini", ".yaml", ".yml", ".json", ".env", ".tf",
    ".sql", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".mk", "Dockerfile",
    "Makefile", "Procfile",
)  # fmt: skip


def _matches(name: str, suffixes) -> bool:
  if name.endswith(suffixes) or name in suffixes:
    return True
  return ".env" in suffixes and name.startswith(".env")


def discover(
    root: Path, exclude: list[str] | None = None, suffixes=(".py",)
) -> list[Path]:
  """Returns the project's files with these suffixes (or exact names), skipping
  virtualenvs and build output."""
  exclude = exclude or []
  out = []
  for dirpath, dirnames, filenames in os.walk(root):
    d = Path(dirpath)
    dirnames[:] = sorted(
        n
        for n in dirnames
        if n not in SKIP_DIRS
        and not (d / n / "pyvenv.cfg").exists()
        and not _excluded((d / n).relative_to(root).as_posix(), exclude)
    )
    for f in sorted(filenames):
      p = d / f
      if _matches(f, suffixes) and not _excluded(
          p.relative_to(root).as_posix(), exclude
      ):
        out.append(p)
  return out


def _excluded(rel: str, patterns: list[str]) -> bool:
  return any(fnmatch.fnmatch(rel, p) for p in patterns)


def _module_name(rel: str) -> tuple[str, bool]:
  parts = rel[: -len(".py")].split("/")
  if parts and parts[0] == "src" and len(parts) > 1:
    parts = parts[1:]
  is_package = parts[-1] == "__init__"
  if is_package:
    parts = parts[:-1]
  return ".".join(parts), is_package


def read_source(path: Path) -> str:
  with open(path, encoding="utf-8", newline="") as fh:  # keep CRLF as-is
    return fh.read()


def string_value(node: cst.CSTNode) -> str | None:
  """The value of a plain (non-f, non-bytes) string literal, else None."""
  if isinstance(node, (cst.SimpleString, cst.ConcatenatedString)):
    value = node.evaluated_value
    return value if isinstance(value, str) else None
  return None


def is_adk(qualname: str | None, *names: str) -> bool:
  """True if `qualname` is an ADK symbol with one of these final names."""
  return (
      qualname is not None
      and qualname.startswith("google.adk.")
      and qualname.rsplit(".", 1)[1] in names
  )


class Module:
  """One parsed file plus a cheap index of its top-level names."""

  def __init__(self, path: Path, rel: str, source: str, tree: cst.Module):
    self.path, self.rel, self.source, self.tree = path, rel, source, tree
    self.name, self.is_package = _module_name(rel)
    self.imports: dict[str, str] = {}
    self.functions: dict[str, cst.FunctionDef] = {}
    self.classes: dict[str, cst.ClassDef] = {}
    # Module-level `NAME = value`; None if NAME is assigned more than once.
    self.assigns: dict[str, cst.BaseExpression | None] = {}
    self._positions = None
    self._calls = None
    self._enclosing: dict[int, cst.ClassDef] = {}
    self._index(tree.body)

  @property
  def uses_adk(self) -> bool:
    return any(v.startswith("google.adk") for v in self.imports.values())

  @property
  def calls(self) -> list[cst.Call]:
    """Every call in the file. Empty unless the file imports google.adk,
    since only those files can refer to ADK classes."""
    if self._calls is None:
      collector = _CallCollector()
      if self.uses_adk:
        self.tree.visit(collector)
      self._calls = collector.calls
      self._enclosing = collector.enclosing
    return self._calls

  def enclosing_class(self, call: cst.Call) -> cst.ClassDef | None:
    """The class whose body contains `call` (one of `self.calls`)."""
    return self._enclosing.get(id(call))

  def pos(self, node: cst.CSTNode) -> CodeRange:
    if self._positions is None:  # only files with findings pay for this
      wrapper = MetadataWrapper(self.tree, unsafe_skip_copy=True)
      self._positions = wrapper.resolve(PositionProvider)
    return self._positions[node]

  def code(self, node: cst.CSTNode) -> str:
    return self.tree.code_for_node(node)

  def qualname(self, expr: cst.BaseExpression) -> str | None:
    """`FT` -> `google.adk.tools.FunctionTool` given `... import FunctionTool as FT`."""
    parts = []
    while isinstance(expr, cst.Attribute):
      parts.append(expr.attr.value)
      expr = expr.value
    if not isinstance(expr, cst.Name):
      return None
    head = expr.value
    if head in self.imports:
      base = self.imports[head]
    elif head in self.functions or head in self.classes or head in self.assigns:
      base = f"{self.name}.{head}" if self.name else head
    else:
      base = head  # a builtin, or something we can't see
    return ".".join([base, *reversed(parts)])

  def resolve_relative(self, level: int, module: str) -> str:
    pkg = self.name.split(".") if self.is_package else self.name.split(".")[:-1]
    if level > 1:
      pkg = pkg[: max(0, len(pkg) - (level - 1))]
    return ".".join(p for p in [".".join(pkg), module] if p)

  def _index(self, body) -> None:
    """Top-level statements, looking inside `if`/`try` (e.g. TYPE_CHECKING)."""
    for stmt in body:
      if isinstance(stmt, cst.FunctionDef):
        self.functions[stmt.name.value] = stmt
      elif isinstance(stmt, cst.ClassDef):
        self.classes[stmt.name.value] = stmt
      elif isinstance(stmt, cst.SimpleStatementLine):
        for small in stmt.body:
          self._index_small(small)
      elif isinstance(stmt, (cst.If, cst.Try)):
        blocks = [stmt.body]
        if isinstance(stmt, cst.If) and isinstance(stmt.orelse, cst.Else):
          blocks.append(stmt.orelse.body)
        if isinstance(stmt, cst.Try):
          blocks += [h.body for h in stmt.handlers]
        for block in blocks:
          if isinstance(block, cst.IndentedBlock):
            self._index(block.body)

  def _index_small(self, node: cst.BaseSmallStatement) -> None:
    if isinstance(node, cst.Import):
      for alias in node.names:
        full = self.code(alias.name)
        if alias.asname:
          self.imports[self.code(alias.asname.name)] = full
        else:
          top = full.split(".")[0]
          self.imports[top] = top
    elif isinstance(node, cst.ImportFrom):
      if isinstance(node.names, cst.ImportStar):
        return
      mod = self.code(node.module) if node.module else ""
      if node.relative:
        mod = self.resolve_relative(len(node.relative), mod)
      for alias in node.names:
        name = self.code(alias.name)
        local = self.code(alias.asname.name) if alias.asname else name
        self.imports[local] = f"{mod}.{name}" if mod else name
    elif isinstance(node, cst.Assign) and len(node.targets) == 1:
      target = node.targets[0].target
      if isinstance(target, cst.Name):
        seen = target.value in self.assigns
        self.assigns[target.value] = None if seen else node.value


def find_all(node: cst.CSTNode, *types: type) -> list:
  """Every node of these types under `node`, in source order."""

  class V(cst.CSTVisitor):

    def __init__(self):
      self.found = []

    def on_visit(self, n: cst.CSTNode) -> bool:
      if isinstance(n, types):
        self.found.append(n)
      return True

  v = V()
  node.visit(v)
  return v.found


class _CallCollector(cst.CSTVisitor):
  """Collects calls, remembering the class each one sits in (for `self.x`)."""

  def __init__(self):
    self.calls: list[cst.Call] = []
    self.enclosing: dict[int, cst.ClassDef] = {}
    self._classes: list[cst.ClassDef] = []

  def visit_ClassDef(self, node: cst.ClassDef) -> None:
    self._classes.append(node)

  def leave_ClassDef(self, node: cst.ClassDef) -> None:
    self._classes.pop()

  def visit_Call(self, node: cst.Call) -> None:
    self.calls.append(node)
    if self._classes:
      self.enclosing[id(node)] = self._classes[-1]


def method_of(cls: cst.ClassDef, name: str) -> cst.FunctionDef | None:
  if isinstance(cls.body, cst.IndentedBlock):
    for stmt in cls.body.body:
      if isinstance(stmt, cst.FunctionDef) and stmt.name.value == name:
        return stmt
  return None


class Project:
  """The project's files. Files that mention google.adk are parsed up front;
  the rest are parsed only when an import resolves to them."""

  def __init__(self, root: Path, files: list[Path], exclude=None):
    self.root = root
    self.exclude = exclude or []
    self.errors: list[tuple[str, str]] = []
    self._sources: dict[str, tuple[Path, str]] = {}
    self._text_files: list[Path] | None = None
    self._parsed: dict[str, Module | None] = {}
    self._by_name: dict[str, list[tuple[str, Path]]] = {}
    self.modules: list[Module] = []  # the modules that import google.adk
    for path in files:
      rel = path.resolve().relative_to(root).as_posix()
      self._by_name.setdefault(_module_name(rel)[0], []).append((rel, path))
      try:
        source = read_source(path)
      except UnicodeDecodeError as e:
        self._parsed[rel] = None
        self.errors.append((rel, str(e)))
        continue
      self._sources[rel] = (path, source)
      if "google" in source and "adk" in source:  # cheap pre-filter
        m = self._parse(rel, path, source)
        if m is not None and m.uses_adk:
          self.modules.append(m)

  def _parse(self, rel: str, path: Path, source: str | None = None):
    if rel not in self._parsed:
      try:
        source = read_source(path) if source is None else source
        self._parsed[rel] = Module(path, rel, source, cst.parse_module(source))
      except (cst.ParserSyntaxError, UnicodeDecodeError) as e:
        self._parsed[rel] = None
        self.errors.append((rel, str(e).splitlines()[0]))
    return self._parsed[rel]

  def modules_containing(self, needle: str) -> list[Module]:
    """Every parseable Python module whose text contains `needle`."""
    out = []
    for rel, (path, source) in self._sources.items():
      if needle in source:
        m = self._parse(rel, path, source)
        if m is not None:
          out.append(m)
    return out

  def text_files(self, *names_or_suffixes: str) -> list[tuple[str, str]]:
    """(relative path, text) of non-Python files such as pyproject.toml."""
    if self._text_files is None:
      self._text_files = discover(self.root, self.exclude, TEXT_FILES)
    out = []
    for path in self._text_files:
      if _matches(path.name, names_or_suffixes):
        try:
          out.append((path.relative_to(self.root).as_posix(), read_source(path)))
        except (UnicodeDecodeError, OSError):
          continue
    return out

  def module(self, name: str, near: Module | None = None) -> Module | None:
    """The module `name`, as imported from `near`.

    In a monorepo or `src/` layout the import name (`app.tools`) is a suffix
    of the path-derived name (`agents.billing.app.tools`), and several agents
    may each have an `app.tools`. Pick the one closest to the importer.
    """
    found = self._by_name.get(name)
    if not found:
      suffix = "." + name
      found = [f for n, fs in self._by_name.items() if n.endswith(suffix) for f in fs]
    if not found or (len(found) > 1 and near is None):
      return None
    rel, path = max(found, key=lambda f: _shared_prefix(f[0], near.rel if near else ""))
    return self._parse(rel, path)

  def _lookup(self, qualname, table, near, depth=0):
    """Finds a top-level def or class, following re-exports like `pkg/__init__`."""
    if not qualname or "." not in qualname or depth > 5:
      return None
    mod_name, name = qualname.rsplit(".", 1)
    m = self.module(mod_name, near)
    if m is None:
      return None
    node = getattr(m, table).get(name)
    if node is not None:
      return m, node
    if name in m.imports:
      return self._lookup(m.imports[name], table, m, depth + 1)
    return None

  def function(self, qualname: str | None, near: Module | None = None):
    """A top-level function, or a method given as `module.Class.method`."""
    hit = self._lookup(qualname, "functions", near)
    if hit is None and qualname and qualname.count(".") >= 2:
      cls_name, meth = qualname.rsplit(".", 1)
      owner = self.cls(cls_name, near)
      if owner is not None and (fn := method_of(owner[1], meth)) is not None:
        hit = owner[0], fn
    return hit

  def cls(self, qualname: str | None, near: Module | None = None):
    return self._lookup(qualname, "classes", near)

  def assign(self, qualname: str | None, near: Module | None = None):
    """A module-level `NAME = value` (one assignment only)."""
    return self._lookup(qualname, "assigns", near)


def _shared_prefix(a: str, b: str) -> int:
  n = 0
  for x, y in zip(a.split("/"), b.split("/")):
    if x != y:
      break
    n += 1
  return n


def load_project(
    root: Path, files: list[Path] | None = None, exclude: list[str] | None = None
) -> Project:
  root = root.resolve()
  if files is not None:  # exactly these files, and no others
    project = Project(root, [f for f in files if f.suffix == ".py"], exclude)
    project._text_files = [f for f in files if f.suffix != ".py"]
    return project
  return Project(root, discover(root, exclude), exclude)
