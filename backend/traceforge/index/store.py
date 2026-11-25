# ruff: noqa: E501
"""Content-addressed vector cache plus per-commit manifests, on disk, model-versioned.

Layout (one namespace per model version AND dims, never mixed):
    <root>/<model_id>@<revision>/<dims>/model.json
                                       /shards/shard-00000001.npz   keys, vecs float32 [n,dims], sums
                                       /manifests/<commit>-<sha12>.json   (immutable, content named)
                                       /ACTIVE.json   single pointer {commit, manifest, sha256}

Atomicity: every file is written to a temp name, flushed, fsynced and os.replace()d. The index
becomes visible only when ACTIVE.json is swapped, so a crash at any earlier point leaves the
previous consistent index untouched (orphan shards are harmless cache entries, and resumable).
Shards are append-only; later shards win on a repeated key. `gc` compacts to live keys.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path

import numpy as np

SCHEMA = 1


class DimensionMismatch(ValueError):
    pass


class ManifestError(RuntimeError):
    pass


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def vec_sum(v: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(v, dtype=np.float32).tobytes()).hexdigest()[:16]


class NamespaceStore:
    def __init__(self, root, model_id: str, revision: str, dims: int):
        self.model_id, self.revision, self.dims = model_id, revision, int(dims)
        self.dir = Path(root) / f"{_safe(model_id)}@{_safe(revision)}" / str(self.dims)
        meta = self.dir / "model.json"
        want = {"model_id": model_id, "revision": revision, "dims": self.dims}
        if meta.exists():
            have = json.loads(meta.read_text("utf-8"))
            if have.get("dims") != self.dims:
                raise DimensionMismatch(
                    f"namespace {self.dir} holds dims={have.get('dims')}, not {dims}"
                )
            if have.get("model_id") != model_id or have.get("revision") != revision:
                raise ManifestError(f"namespace {self.dir} belongs to another model version")
        else:
            atomic_write(meta, json.dumps(want, indent=1).encode())
        self._vec: dict[str, np.ndarray] = {}
        self._sum: dict[str, str] = {}
        self._bad_cache: set[str] = set()
        self._bad_cache_n: int | None = None
        self._load()

    # ---- vectors
    def _shards(self) -> list[Path]:
        d = self.dir / "shards"
        return sorted(d.glob("shard-*.npz")) if d.is_dir() else []

    def _load(self) -> None:
        self._vec, self._sum, self._bad_cache_n = {}, {}, None
        for p in self._shards():
            with np.load(p, allow_pickle=False) as z:
                keys, vecs, sums = z["keys"], z["vecs"], z["sums"]
            if vecs.ndim != 2 or vecs.shape[1] != self.dims:
                raise DimensionMismatch(
                    f"{p.name} has shape {vecs.shape}, namespace dims {self.dims}"
                )
            for k, v, s in zip(keys.tolist(), vecs, sums.tolist(), strict=True):
                self._vec[k], self._sum[k] = v, s

    def corrupt_keys(self) -> list[str]:
        """Keys whose stored vector fails its checksum, has the wrong shape, or is non-finite."""
        bad = []
        for k, v in self._vec.items():
            if v.shape != (self.dims,) or not np.all(np.isfinite(v)) or vec_sum(v) != self._sum[k]:
                bad.append(k)
        return sorted(bad)

    def has(self, key: str) -> bool:
        return key in self._vec and key not in self._bad()

    def _bad(self) -> set[str]:
        if self._bad_cache_n is None:
            self._bad_cache, self._bad_cache_n = set(self.corrupt_keys()), len(self._vec)
        return self._bad_cache

    def get(self, key: str) -> np.ndarray:
        return self._vec[key]

    def keys(self) -> set[str]:
        return set(self._vec)

    def put_many(self, keys: list[str], vecs: np.ndarray) -> None:
        vecs = np.asarray(vecs, dtype=np.float32)
        if vecs.ndim != 2 or vecs.shape[1] != self.dims or vecs.shape[0] != len(keys):
            raise DimensionMismatch(
                f"cannot store shape {vecs.shape} in namespace dims {self.dims}"
            )
        if not keys:
            return
        sums = [vec_sum(v) for v in vecs]
        buf = io.BytesIO()
        np.savez(buf, keys=np.array(keys), vecs=vecs, sums=np.array(sums))
        n = 1 + max((int(p.stem.split("-")[1]) for p in self._shards()), default=0)
        atomic_write(self.dir / "shards" / f"shard-{n:08d}.npz", buf.getvalue())
        for k, v, s in zip(keys, vecs, sums, strict=True):
            self._vec[k], self._sum[k] = v, s
        self._bad_cache_n = None

    def storage_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.dir.rglob("*") if p.is_file())

    def gc(self, retain: str = "all") -> int:
        """Drop vectors not referenced by retained manifests ("all" manifests or only "active"),
        compacting the shards into one. Returns the number of vectors removed."""
        live: set[str] = set()
        if retain == "active":
            act = self.read_active()
            mans = [act[1]] if act else []
        else:
            mans = [
                json.loads(p.read_text("utf-8"))
                for p in sorted((self.dir / "manifests").glob("*.json"))
            ]
        for m in mans:
            live.update(c["embed_key"] for c in m["chunks"])
        keep = sorted(k for k in self._vec if k in live)
        removed = len(self._vec) - len(keep)
        old = self._shards()
        if keep:
            vecs = np.stack([self._vec[k] for k in keep])
            buf = io.BytesIO()
            np.savez(
                buf, keys=np.array(keep), vecs=vecs, sums=np.array([self._sum[k] for k in keep])
            )
            n = 1 + max(int(p.stem.split("-")[1]) for p in old) if old else 1
            atomic_write(self.dir / "shards" / f"shard-{n:08d}.npz", buf.getvalue())
        for p in old:
            p.unlink()
        self._load()
        self._bad_cache_n = None
        return removed

    # ---- manifests and the ACTIVE pointer
    def write_manifest(self, manifest: dict) -> tuple[str, str]:
        data = json.dumps(manifest, sort_keys=True, indent=1).encode()
        digest = hashlib.sha256(data).hexdigest()
        name = f"{_safe(manifest['commit'])}-{digest[:12]}.json"
        atomic_write(self.dir / "manifests" / name, data)
        return name, digest

    def set_active(self, commit: str, name: str, digest: str) -> None:
        ptr = {"schema": SCHEMA, "commit": commit, "manifest": name, "sha256": digest}
        atomic_write(self.dir / "ACTIVE.json", json.dumps(ptr, indent=1).encode())

    def read_active(self) -> tuple[dict, dict] | None:
        """(pointer, manifest) or None when nothing was ever published. Raises ManifestError if
        the pointer is dangling or its manifest hash does not match."""
        p = self.dir / "ACTIVE.json"
        if not p.exists():
            return None
        try:
            ptr = json.loads(p.read_text("utf-8"))
            data = (self.dir / "manifests" / ptr["manifest"]).read_bytes()
        except (OSError, ValueError, KeyError) as exc:
            raise ManifestError(f"invalid ACTIVE pointer: {exc}") from exc
        if hashlib.sha256(data).hexdigest() != ptr.get("sha256"):
            raise ManifestError("manifest hash does not match ACTIVE pointer")
        m = json.loads(data)
        if m.get("dims") != self.dims:
            raise DimensionMismatch(f"manifest dims {m.get('dims')} != namespace dims {self.dims}")
        return ptr, m
