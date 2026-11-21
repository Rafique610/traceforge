"""Programmatic, realistic-looking Python code with exactly one planted bug (P0-S06 Part B).

Not filler: every unit is a small function/class with a docstring and a plausible body. A bug
template has a correct and a buggy body that differ in exactly one line, plus a symptom text
that describes the behaviour without naming the function or the line.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

ENTITIES = [
    "order", "invoice", "shipment", "ticket", "session", "cart", "booking", "payment",
    "account", "report", "message", "task", "customer", "product", "refund", "subscription",
]  # fmt: skip

HEADER = (
    '"""{doc}"""\n\n'
    "import logging\n"
    "from dataclasses import dataclass, field\n"
    "from datetime import date\n\n"
    "logger = logging.getLogger(__name__)\n\n\n"
)


@dataclass
class Unit:
    text: str  # complete source of the unit, ends with two blank lines
    bug_line_offset: int | None = None  # 0-based line inside `text` of the buggy statement
    symptom: str | None = None
    name: str = ""


def _u(body: str, **kw) -> Unit:
    return Unit(text=body.strip("\n") + "\n\n\n", **kw)


# ---- bug templates: (correct_body, buggy_body, symptom). Bodies differ in ONE line. -------------
def _bug_templates(e: str) -> list[tuple[str, str, str, str]]:
    def make(name: str, tmpl: str, wrong: str, right: str, symptom: str):
        body = tmpl.format(e=e)
        return name, body.replace("@@", right), body.replace("@@", wrong), symptom.format(e=e)

    return [
        make(
            f"bulk_discount_{e}",
            "def bulk_discount_{e}(unit_price, quantity):\n"
            '    """Price of a {e} line: 10% off the whole line when quantity is 10 or more."""\n'
            "    total = unit_price * quantity\n"
            "@@\n"
            "        total = total * 0.9\n"
            "    return round(total, 2)",
            "    if quantity > 10:",
            "    if quantity >= 10:",
            "A {e} line with exactly 10 units is charged the full price although 10 units "
            "should already get the bulk discount.",
        ),
        make(
            f"page_of_{e}s",
            "def page_of_{e}s(items, page, size):\n"
            '    """Return one page of {e}s; pages are numbered from 1."""\n'
            "@@\n"
            "    return items[start:start + size]",
            "    start = page * size",
            "    start = (page - 1) * size",
            "Asking for page 1 of the {e} list skips the first items and page 2 starts too late.",
        ),
        make(
            f"mean_{e}_amount",
            "def mean_{e}_amount(amounts):\n"
            '    """Average {e} amount, 0.0 for an empty list."""\n'
            "    if not amounts:\n"
            "        return 0.0\n"
            "@@",
            "    return sum(amounts) / (len(amounts) + 1)",
            "    return sum(amounts) / len(amounts)",
            "The reported average {e} amount is always a little lower than the real average.",
        ),
        make(
            f"{e}_is_expired",
            "def {e}_is_expired(created_at, ttl_seconds, now):\n"
            '    """True when the {e} is older than its time-to-live."""\n'
            "    age = now - created_at\n"
            "@@",
            "    return age < ttl_seconds",
            "    return age > ttl_seconds",
            "Fresh {e} records are reported as expired and old ones are still treated as valid.",
        ),
        make(
            f"{e}_retry_delay",
            "def {e}_retry_delay(attempt, base=0.5):\n"
            '    """Exponential backoff for {e} retries: base, 2*base, 4*base, ..."""\n'
            "@@\n"
            "    return min(delay, 60.0)",
            "    delay = base * (2 * attempt)",
            "    delay = base * (2 ** attempt)",
            "The wait between {e} retries grows linearly instead of doubling each time.",
        ),
        make(
            f"normalize_{e}_key",
            "def normalize_{e}_key(raw):\n"
            '    """Canonical lookup key for a {e}: trimmed and lower case."""\n'
            "    if raw is None:\n"
            '        return ""\n'
            "@@",
            "    return raw.strip()",
            "    return raw.strip().lower()",
            "Two {e} keys that differ only by upper/lower case are stored as separate entries.",
        ),
        make(
            f"merge_{e}_counts",
            "def merge_{e}_counts(left, right):\n"
            '    """Combine two {e} counters by adding the counts of equal keys."""\n'
            "    merged = dict(left)\n"
            "    for key, value in right.items():\n"
            "@@\n"
            "    return merged",
            "        merged[key] = value",
            "        merged[key] = merged.get(key, 0) + value",
            "After merging two {e} counters, keys present in both keep only the second count.",
        ),
        make(
            f"latest_{e}s",
            "def latest_{e}s(items, n):\n"
            '    """The n most recent {e}s; items are sorted oldest first."""\n'
            "    if n <= 0:\n"
            "        return []\n"
            "@@",
            "    return items[-n + 1:]",
            "    return items[-n:]",
            "Asking for the latest N {e}s returns one fewer than requested.",
        ),
        make(
            f"{e}_share_percent",
            "def {e}_share_percent(part, total):\n"
            '    """Share of the total that this {e} group represents, in percent."""\n'
            "    if total == 0:\n"
            "        return 0.0\n"
            "@@",
            "    return round(total * 100.0 / part, 1)",
            "    return round(part * 100.0 / total, 1)",
            "The {e} share report shows values far above 100 for small groups and below 100 "
            "for big ones.",
        ),
        make(
            f"{e}_span_days",
            "def {e}_span_days(start: date, end: date):\n"
            '    """Calendar days covered by a {e}, both the first and the last day included."""\n'
            "@@",
            "    return (end - start).days",
            "    return (end - start).days + 1",
            "A {e} that starts on the 1st and ends on the 3rd is reported as covering 2 days "
            "instead of 3.",
        ),
    ]


N_BUG_TEMPLATES = 10


def bug_unit(idx: int, entity: str) -> Unit:
    name, right, wrong, symptom = _bug_templates(entity)[idx % N_BUG_TEMPLATES]
    # bug line = first line where the two bodies differ
    rl, wl = right.splitlines(), wrong.splitlines()
    off = next(i for i, (a, b) in enumerate(zip(rl, wl, strict=True)) if a != b)
    return _u(wrong, bug_line_offset=off, symptom=symptom, name=name)


def good_bug_unit(idx: int, entity: str) -> Unit:
    name, right, _, _ = _bug_templates(entity)[idx % N_BUG_TEMPLATES]
    return _u(right, name=name)


# ---- distractor units (correct code) --------------------------------------------------------
def _distractors(e: str) -> list[Unit]:
    E = e.capitalize()
    return [
        _u(
            f"@dataclass\nclass {E}Record:\n"
            f'    """Stored fields of one {e}."""\n\n'
            f"    {e}_id: int\n    owner: str\n    amount: float = 0.0\n"
            f"    tags: list[str] = field(default_factory=list)\n"
        ),
        _u(
            f"def validate_{e}(record):\n"
            f'    """Raise ValueError when a {e} record is not usable."""\n'
            f"    if record.{e}_id <= 0:\n"
            f'        raise ValueError("{e} id must be positive")\n'
            f"    if not record.owner:\n"
            f'        raise ValueError("{e} needs an owner")\n'
            f"    if record.amount < 0:\n"
            f'        raise ValueError("{e} amount must not be negative")\n'
            f"    return True"
        ),
        _u(
            f"class {E}Store:\n"
            f'    """In-memory store of {e} records, keyed by id."""\n\n'
            f"    def __init__(self):\n"
            f"        self._items = {{}}\n\n"
            f"    def add(self, record):\n"
            f"        if record.{e}_id in self._items:\n"
            f'            raise KeyError(f"duplicate {e} {{record.{e}_id}}")\n'
            f"        self._items[record.{e}_id] = record\n"
            f'        logger.debug("added {e} %s", record.{e}_id)\n\n'
            f"    def get(self, {e}_id):\n"
            f"        return self._items.get({e}_id)\n\n"
            f"    def remove(self, {e}_id):\n"
            f"        return self._items.pop({e}_id, None)\n\n"
            f"    def __len__(self):\n"
            f"        return len(self._items)\n"
        ),
        _u(
            f"def format_{e}_line(record):\n"
            f'    """One-line text form of a {e} for logs and reports."""\n'
            f'    tags = ",".join(sorted(record.tags)) or "-"\n'
            f'    return f"{e}#{{record.{e}_id}} {{record.owner}} {{record.amount:.2f}} [{{tags}}]"'
        ),
        _u(
            f"def parse_{e}_row(line):\n"
            f'    """Parse "id,owner,amount" into a {E}Record."""\n'
            f'    parts = [p.strip() for p in line.split(",")]\n'
            f"    if len(parts) != 3:\n"
            f'        raise ValueError(f"bad {e} row: {{line!r}}")\n'
            f"    return {E}Record(int(parts[0]), parts[1], float(parts[2]))"
        ),
        _u(
            f"def group_{e}s_by_owner(records):\n"
            f'    """Map owner -> list of that owner\'s {e}s."""\n'
            f"    groups = {{}}\n"
            f"    for record in records:\n"
            f"        groups.setdefault(record.owner, []).append(record)\n"
            f"    return groups"
        ),
        _u(
            f"def total_{e}_amount(records):\n"
            f'    """Sum of all {e} amounts, rounded to cents."""\n'
            f"    total = 0.0\n"
            f"    for record in records:\n"
            f"        total += record.amount\n"
            f"    return round(total, 2)"
        ),
        _u(
            f"def top_{e}_owners(records, limit=3):\n"
            f'    """Owners with the highest summed {e} amount, best first."""\n'
            f"    sums = {{}}\n"
            f"    for record in records:\n"
            f"        sums[record.owner] = sums.get(record.owner, 0.0) + record.amount\n"
            f"    ranked = sorted(sums.items(), key=lambda kv: kv[1], reverse=True)\n"
            f"    return ranked[:limit]"
        ),
        _u(
            f"def archive_old_{e}s(store, cutoff_id):\n"
            f'    """Remove {e}s whose id is below cutoff_id and return how many were removed."""\n'
            f"    removed = 0\n"
            f"    for key in list(store._items):\n"
            f"        if key < cutoff_id:\n"
            f"            store.remove(key)\n"
            f"            removed += 1\n"
            f'    logger.info("archived %d {e}s", removed)\n'
            f"    return removed"
        ),
    ]


MODULES = ["orders", "billing", "shipping", "support", "accounts", "reports", "tasks", "catalog"]


def generate(
    n_lines: int, seed: int, bug_idx: int, bug_pos: float, max_file_lines: int = 200
) -> dict:
    """Return {files: {path: text}, bug_file, bug_line (1-based), symptom, bug_name, n_lines}.

    Units (correct distractors and correct bug-template functions) are shuffled deterministically,
    one buggy unit is inserted at relative position `bug_pos`, then packed into files.
    """
    rng = random.Random(seed)
    ents = ENTITIES[:]
    rng.shuffle(ents)
    bug_ent = ents[0]
    twin = bug_unit(bug_idx, bug_ent).name
    combos = [
        u
        for ent in ents
        for u in _distractors(ent) + [good_bug_unit(k, ent) for k in range(N_BUG_TEMPLATES)]
        if u.name != twin
    ]
    rng.shuffle(combos)
    pool: list[Unit] = []
    est = 0
    for u in combos:
        if est >= n_lines:
            break
        pool.append(u)
        est += u.text.count(chr(10))
    rng.shuffle(pool)
    bug = bug_unit(bug_idx, bug_ent)
    pool.insert(max(0, min(len(pool), int(bug_pos * len(pool)))), bug)

    files: dict[str, str] = {}
    bug_file, bug_line = "", 0
    cur_units: list[Unit] = []
    cur_lines = 0
    chunks: list[list[Unit]] = []
    for u in pool:
        nl = u.text.count("\n")
        if cur_units and cur_lines + nl > max_file_lines:
            chunks.append(cur_units)
            cur_units, cur_lines = [], 0
        cur_units.append(u)
        cur_lines += nl
    if cur_units:
        chunks.append(cur_units)
    for ci, chunk in enumerate(chunks):
        mod = MODULES[ci % len(MODULES)] + ("" if ci < len(MODULES) else str(ci))
        path = f"shop/{mod}.py"
        text = HEADER.format(doc=f"{mod.capitalize()} helpers for the shop backend.")
        for u in chunk:
            if u is bug:
                bug_file = path
                bug_line = text.count("\n") + 1 + u.bug_line_offset
            text += u.text
        files[path] = text.rstrip("\n") + "\n"
    total = sum(t.count("\n") for t in files.values())
    return {
        "files": files,
        "bug_file": bug_file,
        "bug_line": bug_line,
        "symptom": bug.symptom,
        "bug_name": bug.name,
        "n_lines": total,
    }


def fixed_version(gen: dict, bug_idx: int) -> dict[str, str]:
    """Same files with the buggy unit replaced by its correct twin (for scoring fixes)."""
    ent = next(e for e in ENTITIES if bug_unit(bug_idx, e).name == gen["bug_name"])
    wrong = bug_unit(bug_idx, ent).text.strip("\n")
    right = good_bug_unit(bug_idx, ent).text.strip("\n")
    out = dict(gen["files"])
    assert out[gen["bug_file"]].count(wrong) == 1
    out[gen["bug_file"]] = out[gen["bug_file"]].replace(wrong, right, 1)
    return out


# ---- write-limit module: N independent one-line defects -------------------------------------
def rates_module(n_bugs: int, seed: int) -> dict:
    """A tax-rate module with `n_bugs` functions whose one changed line contradicts the docstring,
    plus decoy functions that are correct. Each wrong line is unique (it names its constant)."""
    rng = random.Random(seed)
    n_ok = max(3, n_bugs // 4)
    total = n_bugs + n_ok
    names = [f"zone_{i:03d}" for i in range(total)]
    rates = {n: rng.choice([5, 6, 7, 8, 9, 10, 12, 15, 19, 20, 21, 25]) for n in names}
    bug_names = set(rng.sample(names, n_bugs))
    consts = "\n".join(f"RATE_{n.upper()} = {rates[n] / 100:.2f}" for n in names)
    head = '"""Sales tax per delivery zone."""\n\n' + consts + "\n\n\n"
    wrong_forms = [
        "    return round(amount * RATE_{N}, 2)",
        "    return round(amount + RATE_{N}, 2)",
        "    return round(amount * (1 - RATE_{N}), 2)",
    ]
    right = "    return round(amount * (1 + RATE_{N}), 2)"
    bad, good = head, head
    changed = 0
    for k, n in enumerate(names):
        N = n.upper()
        pre = (
            f"def tax_{n}(amount):\n"
            f'    """Return amount plus the {n} sales tax (RATE_{N}), rounded to cents."""\n'
        )
        r_line = right.format(N=N)
        w_line = wrong_forms[k % 3].format(N=N) if n in bug_names else r_line
        changed += n in bug_names
        bad += pre + w_line + "\n\n\n"
        good += pre + r_line + "\n\n\n"
    tests = (
        "from shop.rates import tax_zone_000\n\n\n"
        "def test_tax_zone_000():\n"
        f"    assert tax_zone_000(100.0) == {round(100 * (1 + rates['zone_000'] / 100), 2)}\n"
    )
    return {
        "files": {"shop/rates.py": bad.rstrip("\n") + "\n", "tests/test_rates.py": tests},
        "fixed": {"shop/rates.py": good.rstrip("\n") + "\n", "tests/test_rates.py": tests},
        "n_changed_lines": changed,
        "n_functions": total,
    }
