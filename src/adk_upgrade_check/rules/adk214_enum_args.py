"""2.14.0: FunctionTool passes Enum tool arguments as members, not strings.

A tool parameter annotated `Enum`, `Optional[Enum]` or `list[Enum]` used to
receive the raw string the model sent. It now receives the enum member, so
for a plain `Enum`, `arg == "value"`, string-keyed dict lookups, `match` on
strings, `json.dumps` and string methods stop working. For any Enum,
`str(arg)` and f-strings render `Cls.MEMBER` instead of the value.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst
from packaging.version import Version

from ..engine import is_adk
from ..engine import Module
from ..engine import Project
from ..engine import string_value
from .base import Rule

# Enum base -> kind. None means comparisons with the value keep working.
_ENUM_BASES = {
    "enum.Enum": "plain",
    "enum.Flag": "plain",
    "enum.IntEnum": None,
    "enum.IntFlag": None,
    "enum.StrEnum": None,
}
_STR_METHODS = {n for n in dir(str) if not n.startswith("_")}
_OPTIONAL = {"typing.Optional", "Optional"}
_UNION = {"typing.Union", "Union"}
_LIST = {
    "list", "typing.List", "List", "typing.Sequence", "Sequence",
    "collections.abc.Sequence",
}  # fmt: skip
_EMPTY = cst.Module(body=[])


@dataclass
class _Enum:
  kind: str  # "plain" or "str" (a `(str, Enum)` mixin)
  members: dict[str, str]  # string value -> member name


@dataclass
class _Param:
  name: str
  cls_code: str  # how the annotation spells the class, e.g. `models.Plan`
  enum: _Enum
  container: str  # "scalar" or "list"


class EnumArgs(Rule):
  id = "ADK214-ENUM-ARGS"
  introduced_in = Version("2.14.0")
  severity = "error"
  title = "Enum tool arguments arrive as enum members, not strings"
  changelog_url = "https://github.com/google/adk-python/commit/82fe029b8490479229dbfc33815468fe17a427ab"

  def check(self, project):
    for m, fn in _tool_functions(project):
      for param in _enum_params(project, m, fn):
        yield from self._check_param(m, fn, param)

  def _check_param(self, m: Module, fn: cst.FunctionDef, p: _Param):
    uses = _Uses()
    fn.body.visit(uses)
    if p.name in uses.rebound:
      return  # e.g. `plan = Plan(plan)`: too dynamic to judge statically
    plain = p.enum.kind == "plain"
    is_p = lambda n: isinstance(n, cst.Name) and n.value == p.name
    cls = p.cls_code

    for c in uses.comparisons:
      ops = [c.left] + [t.comparator for t in c.comparisons]
      for i, t in enumerate(c.comparisons):
        a, b = ops[i], ops[i + 1]
        op = t.operator
        if p.container == "scalar" and isinstance(op, (cst.Equal, cst.NotEqual)):
          if not plain:
            continue
          lit = b if is_p(a) else a if is_p(b) else None
          if lit is None or string_value(lit) is None:
            continue
          value = string_value(lit)
          member = p.enum.members.get(value)
          always = "False" if isinstance(op, cst.Equal) else "True"
          yield self.finding(
              m,
              lit,
              f"`{m.code(c)}` compares Enum tool argument `{p.name}` with a"
              f" string. From 2.14.0 FunctionTool passes {cls} members, so"
              f" this is always {always}.",
              f"compare against `{cls}.{member}`"
              if member
              else f"compare `{p.name}.value`, or against a `{cls}` member",
              replacement=f"{cls}.{member}" if member else None,
          )
        elif isinstance(op, (cst.In, cst.NotIn)) and plain:
          if (
              p.container == "scalar"
              and is_p(a)
              and _all_strings(b)
          ) or (p.container == "list" and string_value(a) is not None and is_p(b)):
            yield self.finding(
                m,
                c,
                f"`{m.code(c)}` checks Enum tool argument `{p.name}` against"
                f" strings. From 2.14.0 FunctionTool passes {cls} members,"
                " so this never matches.",
                f"check against `{cls}` members, or use `.value`",
            )

    if p.container != "scalar":
      return

    for match in uses.matches:
      if not (plain and is_p(match.subject)):
        continue
      for case in match.cases:
        if _has_string_value_pattern(case.pattern):
          yield self.finding(
              m,
              case.pattern,
              f"`match {p.name}` has string `case` patterns. From 2.14.0"
              f" FunctionTool passes {cls} members, so these never match.",
              f"match on `{cls}.MEMBER` patterns, or `match {p.name}.value`",
          )
          break

    for call in uses.calls:
      qn = m.qualname(call.func)
      if plain and qn == "json.dumps" and any(
          p.name in _bare_names(a.value) for a in call.args
      ):
        yield self.finding(
            m,
            call,
            f"`json.dumps` receives Enum tool argument `{p.name}`. From"
            f" 2.14.0 it is a {cls} member, which json cannot serialize.",
            f"pass `{p.name}.value`",
        )
      elif (
          plain
          and isinstance(call.func, cst.Attribute)
          and is_p(call.func.value)
          and call.func.attr.value in _STR_METHODS
      ):
        yield self.finding(
            m,
            call,
            f"`{m.code(call)}` calls a str method on Enum tool argument"
            f" `{p.name}`. From 2.14.0 it is a {cls} member, so this raises"
            " AttributeError.",
            f"call it on `{p.name}.value`",
        )
      elif qn == "str" and len(call.args) == 1 and is_p(call.args[0].value):
        yield self._renders_member(m, call, p)

    for fexpr in uses.fstring_exprs:
      if is_p(fexpr.expression) and fexpr.conversion in (None, "s"):
        yield self._renders_member(m, fexpr, p)

    for binop in uses.binops:
      sides = (binop.left, binop.right)
      if plain and isinstance(binop.operator, cst.Add) and any(
          is_p(s) for s in sides
      ) and any(
          string_value(s) is not None or isinstance(s, cst.FormattedString)
          for s in sides
      ):
        yield self.finding(
            m,
            binop,
            f"`{m.code(binop)}` concatenates Enum tool argument `{p.name}`"
            f" with a string. From 2.14.0 it is a {cls} member, so this"
            " raises TypeError.",
            f"use `{p.name}.value`",
        )

    for sub in uses.subscripts:
      if not (plain and isinstance(sub.value, cst.Name)):
        continue
      if len(sub.slice) != 1 or not isinstance(sub.slice[0].slice, cst.Index):
        continue
      if not is_p(sub.slice[0].slice.value):
        continue
      d = uses.local_dicts.get(sub.value.value) or m.assigns.get(sub.value.value)
      if isinstance(d, cst.Dict) and d.elements and all(
          isinstance(e, cst.DictElement) and string_value(e.key) is not None
          for e in d.elements
      ):
        yield self.finding(
            m,
            sub,
            f"`{m.code(sub)}` looks up a string-keyed dict with Enum tool"
            f" argument `{p.name}`. From 2.14.0 it is a {cls} member, so"
            " this raises KeyError.",
            f"use `{sub.value.value}[{p.name}.value]`, or key the dict by"
            f" {cls} members",
        )

  def _renders_member(self, m: Module, node: cst.CSTNode, p: _Param):
    return self.finding(
        m,
        node,
        f"`{m.code(node)}` renders Enum tool argument `{p.name}` as text. From"
        f" 2.14.0 it is a {p.cls_code} member, so this gives"
        f" `{p.cls_code.rsplit('.', 1)[-1]}.MEMBER` instead of the value.",
        f"use `{p.name}.value`",
        severity="warning",
    )


# --- tool discovery -------------------------------------------------------


def _tool_functions(project: Project):
  """Functions passed to an ADK agent's `tools=[...]` or to `FunctionTool(...)`."""
  seen = {}
  for m in project.modules:
    for call in m.calls:
      qn = m.qualname(call.func)
      exprs = []
      if is_adk(qn, "Agent", "LlmAgent"):
        exprs = [a.value for a in call.args if a.keyword and a.keyword.value == "tools"]
      elif is_adk(qn, "FunctionTool", "LongRunningFunctionTool"):
        for i, arg in enumerate(call.args):
          if (arg.keyword and arg.keyword.value == "func") or (
              i == 0 and arg.keyword is None and not arg.star
          ):
            exprs.append(arg.value)
      for ref_m, ref in _expand_tools(project, m, exprs):
        hit = project.function(ref_m.qualname(ref), near=ref_m)
        if hit:
          seen[(hit[0].name, hit[1].name.value)] = hit
  return list(seen.values())


def _expand_tools(project: Project, m: Module, exprs, depth: int = 0):
  """Yields (module, expr) per tool, following `tools=ALL_TOOLS`-style lists."""
  for e in exprs:
    if isinstance(e, (cst.List, cst.Tuple)):
      # Element.value, or the list being unpacked for a `*STARRED` element
      yield from _expand_tools(project, m, [el.value for el in e.elements], depth)
    elif isinstance(e, cst.BinaryOperation) and isinstance(e.operator, cst.Add):
      yield from _expand_tools(project, m, [e.left, e.right], depth)
    elif isinstance(e, (cst.Name, cst.Attribute)) and depth < 5:
      hit = project.assign(m.qualname(e), near=m)
      if hit and isinstance(hit[1], (cst.List, cst.Tuple, cst.BinaryOperation)):
        yield from _expand_tools(project, hit[0], [hit[1]], depth + 1)
      else:
        yield m, e
    else:
      yield m, e


def _enum_params(project: Project, m: Module, fn: cst.FunctionDef):
  params = fn.params
  for param in [*params.posonly_params, *params.params, *params.kwonly_params]:
    if param.annotation is None:
      continue
    unwrapped = _unwrap(m, param.annotation.annotation)
    if unwrapped is None:
      continue
    cls_node, container = unwrapped
    info = _enum_info(project, m.qualname(cls_node), m)
    if info is not None:
      yield _Param(param.name.value, _EMPTY.code_for_node(cls_node), info, container)


def _unwrap(m: Module, ann: cst.BaseExpression):
  """`Optional[list[Plan]]` -> (Plan, "list"); None if not a simple class."""
  container = "scalar"
  if isinstance(ann, cst.SimpleString):  # a "Plan" forward reference
    try:
      ann = cst.parse_expression(ann.evaluated_value)
    except cst.ParserSyntaxError:
      return None
  for _ in range(4):
    if isinstance(ann, cst.BinaryOperation) and isinstance(
        ann.operator, cst.BitOr
    ):
      rest = [s for s in (ann.left, ann.right) if not _is_none(s)]
      if len(rest) != 1:
        return None
      ann = rest[0]
    elif isinstance(ann, cst.Subscript):
      qn = m.qualname(ann.value)
      elems = [
          e.slice.value for e in ann.slice if isinstance(e.slice, cst.Index)
      ]
      if qn in _OPTIONAL | _UNION:
        rest = [e for e in elems if not _is_none(e)]
        if len(rest) != 1:
          return None
        ann = rest[0]
      elif qn in _LIST and len(elems) == 1 and container == "scalar":
        container, ann = "list", elems[0]
      else:
        return None
    else:
      break
  if isinstance(ann, (cst.Name, cst.Attribute)):
    return ann, container
  return None


def _enum_info(project: Project, qualname: str | None, near: Module, depth=0):
  hit = project.cls(qualname, near)
  if hit is None or depth > 5:
    return None
  m, node = hit
  kind, has_str = None, False
  for base in node.bases:
    bq = m.qualname(base.value)
    if bq == "str":
      has_str = True
    elif bq in _ENUM_BASES:
      if _ENUM_BASES[bq] is None:
        return None
      kind = "plain"
    else:
      parent = _enum_info(project, bq, m, depth + 1)
      if parent is not None:
        kind = parent.kind
  if kind is None:
    return None
  members = {}
  if isinstance(node.body, cst.IndentedBlock):
    for stmt in node.body.body:
      if not isinstance(stmt, cst.SimpleStatementLine):
        continue
      for small in stmt.body:
        if (
            isinstance(small, cst.Assign)
            and len(small.targets) == 1
            and isinstance(small.targets[0].target, cst.Name)
        ):
          value = string_value(small.value)
          if value is not None:
            members.setdefault(value, small.targets[0].target.value)
  return _Enum("str" if has_str else kind, members)


# --- helpers --------------------------------------------------------------


def _is_none(node: cst.BaseExpression) -> bool:
  return isinstance(node, cst.Name) and node.value == "None"


def _all_strings(node: cst.BaseExpression) -> bool:
  if not isinstance(node, (cst.Tuple, cst.List, cst.Set)) or not node.elements:
    return False
  return all(string_value(e.value) is not None for e in node.elements)


def _has_string_value_pattern(pattern: cst.MatchPattern) -> bool:
  if isinstance(pattern, cst.MatchValue):
    return string_value(pattern.value) is not None
  if isinstance(pattern, cst.MatchOr):
    return any(_has_string_value_pattern(p.pattern) for p in pattern.patterns)
  if isinstance(pattern, cst.MatchAs) and pattern.pattern is not None:
    return _has_string_value_pattern(pattern.pattern)
  return False


def _bare_names(node: cst.CSTNode) -> set[str]:
  """Names used directly in `node`, not as the base of `x.attr`."""

  class V(cst.CSTVisitor):

    def __init__(self):
      self.names: set[str] = set()

    def visit_Attribute(self, n: cst.Attribute) -> bool:
      return False  # `plan.value` is fine; don't look inside

    def visit_Name(self, n: cst.Name) -> None:
      self.names.add(n.value)

  v = V()
  node.visit(v)
  return v.names


def _target_names(node: cst.CSTNode) -> set[str]:
  if isinstance(node, cst.Name):
    return {node.value}
  if isinstance(node, (cst.Tuple, cst.List)):
    return set().union(*(_target_names(e.value) for e in node.elements))
  if isinstance(node, cst.StarredElement):
    return _target_names(node.value)
  return set()  # attribute and subscript targets don't rebind a name


class _Uses(cst.CSTVisitor):
  """One pass over a function body, collecting the nodes the checks need."""

  def __init__(self):
    self.rebound: set[str] = set()
    self.comparisons: list[cst.Comparison] = []
    self.matches: list[cst.Match] = []
    self.calls: list[cst.Call] = []
    self.fstring_exprs: list[cst.FormattedStringExpression] = []
    self.binops: list[cst.BinaryOperation] = []
    self.subscripts: list[cst.Subscript] = []
    self.local_dicts: dict[str, cst.Dict] = {}

  def visit_Assign(self, node: cst.Assign) -> None:
    for t in node.targets:
      self.rebound |= _target_names(t.target)
      if isinstance(t.target, cst.Name) and isinstance(node.value, cst.Dict):
        self.local_dicts[t.target.value] = node.value

  def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
    if node.value is not None:
      self.rebound |= _target_names(node.target)

  def visit_AugAssign(self, node: cst.AugAssign) -> None:
    self.rebound |= _target_names(node.target)

  def visit_For(self, node: cst.For) -> None:
    self.rebound |= _target_names(node.target)

  def visit_CompFor(self, node: cst.CompFor) -> None:
    self.rebound |= _target_names(node.target)

  def visit_WithItem(self, node: cst.WithItem) -> None:
    if node.asname is not None:
      self.rebound |= _target_names(node.asname.name)

  def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
    self.rebound |= _target_names(node.target)

  def visit_Comparison(self, node: cst.Comparison) -> None:
    self.comparisons.append(node)

  def visit_Match(self, node: cst.Match) -> None:
    self.matches.append(node)

  def visit_Call(self, node: cst.Call) -> None:
    self.calls.append(node)

  def visit_FormattedStringExpression(
      self, node: cst.FormattedStringExpression
  ) -> None:
    self.fstring_exprs.append(node)

  def visit_BinaryOperation(self, node: cst.BinaryOperation) -> None:
    self.binops.append(node)

  def visit_Subscript(self, node: cst.Subscript) -> None:
    self.subscripts.append(node)
