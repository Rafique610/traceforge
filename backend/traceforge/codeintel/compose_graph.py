"""Compose YAML, Dockerfile CMD and .env key names -> service / config-key nodes and edges.

Only .env KEY NAMES are read (values are never stored). Not cached: these files are few.
"""

import json
import posixpath
import re
import shlex
from pathlib import Path

import yaml

from .builder import Builder, ModuleIndex

COMPOSE_RE = re.compile(r"^(docker-)?compose([.-].+)?\.ya?ml$")
DOTENV_RE = re.compile(r"^\.env(\..+)?$")
_KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def is_compose(name: str) -> bool:
    return bool(COMPOSE_RE.match(name))


def is_dotenv(name: str) -> bool:
    return bool(DOTENV_RE.match(name))


def dotenv_keys(text: str) -> list[dict]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = _KEY_LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            out.append({"key": m.group(1), "line": i})
    return out


def _scalar(n) -> str | None:
    return n.value if isinstance(n, yaml.ScalarNode) else None


def _pairs(n) -> list[tuple[str, yaml.Node, yaml.Node]]:
    """(name, key node, value node) of a mapping, expanding YAML `<<` merge keys (own keys win)."""
    if not isinstance(n, yaml.MappingNode):
        return []
    own, merged = {}, {}
    for k, v in n.value:
        if not isinstance(k, yaml.ScalarNode):
            continue
        if k.value == "<<":
            for src in v.value if isinstance(v, yaml.SequenceNode) else [v]:
                for name, kk, vv in _pairs(src):
                    merged.setdefault(name, (kk, vv))
        else:
            own[k.value] = (k, v)
    return [(name, *kv) for name, kv in {**merged, **own}.items()]


def _map(n) -> dict:
    return {name: v for name, _k, v in _pairs(n)}


def _seq_scalars(n) -> list[tuple[str, int]]:
    if isinstance(n, yaml.SequenceNode):
        return [(c.value, c.start_mark.line + 1) for c in n.value if isinstance(c, yaml.ScalarNode)]
    if isinstance(n, yaml.ScalarNode):
        return [(n.value, n.start_mark.line + 1)]
    return []


def _env(n) -> list[tuple[str, int]]:
    if isinstance(n, yaml.MappingNode):
        return [(name, k.start_mark.line + 1) for name, k, _v in _pairs(n)]
    return [(s.split("=", 1)[0], ln) for s, ln in _seq_scalars(n)]


def _dockerfile_cmd(path: Path) -> list[str] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    cmd = None
    for line in lines:
        m = re.match(r"\s*(CMD|ENTRYPOINT)\s+(.*)$", line, re.I)
        if m:
            body = m.group(2).strip()
            try:
                cmd = json.loads(body) if body.startswith("[") else shlex.split(body)
            except ValueError:
                continue
    return cmd


def entry_file(tokens: list[str], bases: list[str], idx: ModuleIndex) -> str | None:
    """Python file a service command runs: `-m pkg`, `script.py`, or `pkg.mod:app`."""
    toks = [str(t) for t in tokens]
    near = (bases[0] + "/x") if bases else "x"
    if "-m" in toks and toks.index("-m") + 1 < len(toks):
        mod = toks[toks.index("-m") + 1]
        return idx.lookup(mod + ".__main__", near) or idx.lookup(mod, near)
    for t in toks:
        if t.endswith(".py"):
            for b in bases:
                p = posixpath.normpath(posixpath.join(b, t))
                if p in idx.files:
                    return p
            return idx.lookup(t[:-3].replace("/", "."), near)
    for t in toks:
        if ":" in t and not t.startswith("-") and "/" not in t:
            return idx.lookup(t.split(":")[0], near)
    return None


def _command_tokens(cmd, build, root: Path, ctx_dir: str) -> tuple[list[str] | None, int | None]:
    if cmd is not None:
        line = cmd.start_mark.line + 1
        if isinstance(cmd, yaml.SequenceNode):
            return [s for s, _ in _seq_scalars(cmd)], line
        if isinstance(cmd, yaml.ScalarNode):
            return shlex.split(cmd.value), line
        return None, None
    if build is not None:
        dockerfile = _scalar(_map(build).get("dockerfile")) or "Dockerfile"
        return _dockerfile_cmd(root / ctx_dir / dockerfile), None
    return None, None


def add_compose(
    b: Builder,
    root: Path,
    composes: dict[str, str],
    dotenvs: dict[str, list[dict]],
    idx: ModuleIndex,
) -> None:
    for rel, text in sorted(composes.items()):
        try:
            doc = yaml.compose(text)
        except yaml.YAMLError:
            continue
        cdir = posixpath.dirname(rel)
        for name, svc in sorted(_map(_map(doc).get("services")).items()):
            line0 = svc.start_mark.line + 1
            sid = b.node(
                f"svc:{name}", "service", path=rel, start=line0, end=svc.end_mark.line, name=name
            )
            fields = _map(svc)
            for key, line in _env(fields.get("environment")):
                kid = b.node(f"cfg:{key}", "config_key", path=rel, start=line, end=line, name=key)
                b.edge(sid, kid, "service_env", "compose", f"{rel}:{line}")
                b.edge(kid, f"file:{rel}", "defined_in", "compose", f"{rel}:{line}")
            for ef, _line in _seq_scalars(fields.get("env_file")):
                erel = posixpath.normpath(posixpath.join(cdir, ef))
                for k in dotenvs.get(erel, []):
                    b.node(
                        f"cfg:{k['key']}",
                        "config_key",
                        path=erel,
                        start=k["line"],
                        end=k["line"],
                        name=k["key"],
                    )
                    b.edge(sid, f"cfg:{k['key']}", "service_env", "dotenv", f"{erel}:{k['line']}")
            deps = fields.get("depends_on")
            dep_names = (
                [(name, k.start_mark.line + 1) for name, k, _v in _pairs(deps)]
                if isinstance(deps, yaml.MappingNode)
                else _seq_scalars(deps)
            )
            for dn, line in dep_names:
                b.edge(sid, f"svc:{dn}", "depends_on", "compose", f"{rel}:{line}")
            build = fields.get("build")
            ctx = _scalar(build) or _scalar(_map(build).get("context")) or "."
            ctx_dir = posixpath.normpath(posixpath.join(cdir, ctx))
            tokens, line = _command_tokens(
                fields.get("command") or fields.get("entrypoint"), build, root, ctx_dir
            )
            if tokens:
                entry = entry_file(tokens, [ctx_dir, cdir], idx)
                if entry:
                    b.edge(
                        sid, f"file:{entry}", "service_runs", "compose", f"{rel}:{line or line0}"
                    )


def add_dotenv(b: Builder, dotenvs: dict[str, list[dict]]) -> None:
    for rel, keys in sorted(dotenvs.items()):
        for k in keys:
            kid = b.node(
                f"cfg:{k['key']}",
                "config_key",
                path=rel,
                start=k["line"],
                end=k["line"],
                name=k["key"],
            )
            b.edge(kid, f"file:{rel}", "defined_in", "dotenv", f"{rel}:{k['line']}")
