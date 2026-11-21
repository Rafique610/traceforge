"""Mutable node/edge accumulator and the module-name index used while assembling a graph."""

from collections import defaultdict

from .config import REVERSE_OF, SOURCES


class Builder:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights
        self.unknown_conf = 0.2
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}

    def node(self, nid: str, kind: str, **attrs) -> str:
        cur = self.nodes.setdefault(nid, {"kind": kind})
        for k, v in attrs.items():
            cur.setdefault(k, v)  # first declaration wins
        return nid

    def edge(self, src, dst, etype, source, prov, conf=1.0, **extra) -> None:
        if source not in SOURCES or etype not in REVERSE_OF:
            raise ValueError(f"bad edge {etype}/{source}")
        key = (src, dst, etype, prov)
        if key not in self.edges:
            self.edges[key] = {
                "type": etype,
                "source": source,
                "confidence": conf,
                "provenance": prov,
                "weight": self.weights[etype],
                **extra,
            }


class ModuleIndex:
    """Dotted-name -> python file lookup through path-suffix matching (no sys.path needed)."""

    def __init__(self, files: list[str], root_pkg: str | None = None):
        self.files = set(files)
        self.tails: dict[str, list[str]] = defaultdict(list)
        for f in sorted(files):
            parts = ([root_pkg] if root_pkg else []) + f[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            for i in range(len(parts)):
                self.tails[".".join(parts[i:])].append(f)

    @staticmethod
    def _near(cands: list[str], near: str) -> str:
        def common(f: str) -> int:
            n = 0
            for x, y in zip(f.split("/")[:-1], near.split("/")[:-1], strict=False):
                if x != y:
                    break
                n += 1
            return n

        return max(cands, key=lambda f: (common(f), -len(f), f))

    def lookup(self, dotted: str, near: str) -> str | None:
        c = self.tails.get(dotted)
        return self._near(c, near) if c else None

    def relative(self, importer: str, level: int, dotted: str) -> str | None:
        base = importer.split("/")[:-1]
        if level > 1:
            base = base[: len(base) - (level - 1)]
        parts = [*base, *([p for p in dotted.split(".") if p] if dotted else [])]
        path = "/".join(parts)
        for cand in (path + ".py", path + "/__init__.py"):
            if cand in self.files:
                return cand
        return None
