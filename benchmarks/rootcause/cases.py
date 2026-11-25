"""Hand-written cases for the reduced P5-S16 root-cause / impact evaluation.

EVERYTHING here is written by hand BEFORE any tool run. Expected relationships (`chain`, `gold`,
`decoys`, `expected_dependants`, `expected_flags`, `predicted_failing`) come from reading the
template source in templates.py and applying the stated edit; they are not derived from the
analysis tool's output. `run_eval` later compares tool output against them, and compares
`predicted_failing` with the failures MEASURED by running pytest (disagreement is reported).

Refs: "path::Qual.name" is a function/method/class; "cfg:KEY" is a config key.
Edits: (path, old, new) replaces the unique text `old`; (path, None, content) creates a file.
For family F the edits are the patch applied to the CLEAN tree (all tests pass before it); for
every other family the edits are applied to the clean tree to create the buggy repo.
"""

P_ = "app/pricing.py"
M_ = "app/money.py"
I_ = "app/inventory.py"
O_ = "app/orders.py"
C_ = "app/cache.py"
S_ = "app/settings.py"
CMP = "compose.yaml"

_TAGS = "from app.util import normalize\n\n" + "".join(
    f"\ndef tag_{i:02d}(x):\n    return normalize(x)\n\n" for i in range(14)
)

CASES: list[dict] = [
    # ------------------------------------------------------------------ A: same file
    dict(
        id="A1", family="A", project="S",
        title="sign error inside the function the failing test calls",
        edits=[(P_, "return round_money(amount - apply_pct(amount, pct))",
                "return round_money(amount + apply_pct(amount, pct))")],
        primary_test="tests/test_pricing.py::test_discount",
        entry="app/pricing.py::discount",
        chain=["app/pricing.py::discount"],
        gold=["app/pricing.py::discount"], gold_files=[P_],
        extra_deps=["app/money.py::apply_pct", "app/money.py::round_money"],
        decoys=["app/money.py::apply_pct"],
        derivation=(
            "test_discount calls discount(200, 10) directly and expects 180. The edited body adds "
            "the percentage (220), so the defect is the sign in discount itself. apply_pct and "
            "round_money are unchanged and covered by passing tests in test_money.py."
        ),
    ),
    dict(
        id="A2", family="A", project="S",
        title="tax doubled; symptom entry gross and cause tax live in the same file",
        edits=[(P_, "return round_money(amount * settings.TAX_RATE)",
                "return round_money(amount * settings.TAX_RATE * 2)")],
        primary_test="tests/test_pricing.py::test_gross_plain",
        entry="app/pricing.py::gross",
        chain=["app/pricing.py::gross", "app/pricing.py::tax"],
        gold=["app/pricing.py::tax"], gold_files=[P_],
        extra_deps=["app/pricing.py::net_price", "app/pricing.py::discount"],
        decoys=["app/pricing.py::discount", "app/pricing.py::net_price"],
        derivation=(
            "test_gross_plain calls gross(100, 1) and expects 120 = 100 + 20 tax. gross calls tax "
            "(same file). The edit doubles the tax so gross returns 140. net_price and discount "
            "are untouched and give 100 for these arguments."
        ),
    ),
    # ------------------------------------------------------------------ B: other file
    dict(
        id="B1", family="B", project="S",
        title="gross drops the tax; failing test enters through orders.quote",
        edits=[(P_, "    return round_money(net + tax(net))", "    return round_money(net)")],
        primary_test="tests/test_orders.py::test_quote",
        entry="app/orders.py::quote",
        chain=["app/orders.py::quote", "app/pricing.py::gross"],
        gold=["app/pricing.py::gross"], gold_files=[P_],
        extra_deps=["app/pricing.py::discount", "app/pricing.py::net_price", "app/pricing.py::tax"],
        decoys=["app/pricing.py::tax", "app/pricing.py::discount"],
        derivation=(
            "test_quote calls orders.quote(50, 2, 10) expecting 108 (net 100, 10% off = 90, tax "
            "18). quote only forwards to pricing.gross (other file, one call hop). The edit makes "
            "gross return the pre-tax 90. tax itself is correct (test_tax passes)."
        ),
    ),
    dict(
        id="B2", family="B", project="S",
        title="off-by-one in Stock.reserve; test enters through orders.create_order",
        edits=[(I_, "if qty > self.available(sku):", "if qty >= self.available(sku):")],
        primary_test="tests/test_orders.py::test_create_order_exact_stock",
        entry="app/orders.py::create_order",
        chain=["app/orders.py::create_order", "app/inventory.py::Stock.reserve"],
        gold=["app/inventory.py::Stock.reserve"], gold_files=[I_],
        extra_deps=["app/inventory.py::Stock.available", "app/pricing.py::gross"],
        decoys=["app/inventory.py::Stock.available", "app/inventory.py::Stock.add"],
        derivation=(
            "The test reserves exactly the stock (3 of 3). create_order calls stock.reserve "
            "(another file, one hop; the receiver is a parameter so the static edge is only "
            "name-resolved). The edit turns > into >=, so reserving all stock raises ValueError "
            "'insufficient stock'. Stock.available and Stock.add are correct."
        ),
    ),
    dict(
        id="B3", family="B", project="L",
        title="currency conversion inverted; test enters through transfer.transfer",
        edits=[("app/convert.py", "amount / lookup(src) * lookup(dst)",
                "amount * lookup(src) / lookup(dst)")],
        primary_test="tests/test_transfer.py::test_transfer_converts",
        entry="app/transfer.py::transfer",
        chain=["app/transfer.py::transfer", "app/convert.py::convert"],
        gold=["app/convert.py::convert"], gold_files=["app/convert.py"],
        extra_deps=["app/rates.py::lookup"],
        decoys=["app/rates.py::lookup", "app/accounts.py::Account.withdraw"],
        derivation=(
            "transfer(a, b, 100) USD->EUR must return 90 (100 / 1.0 * 0.9). transfer calls "
            "convert (other file, one hop). The edit computes 100 * 1.0 / 0.9 = 111.11. lookup "
            "returns the correct rate (test_lookup passes) and withdraw/deposit are not involved "
            "in the returned value."
        ),
    ),
    dict(
        id="B4", family="B", project="S",
        title="Stock.add overwrites instead of accumulating (state written by the test)",
        edits=[(I_, "self.items[sku] = self.available(sku) + qty", "self.items[sku] = qty")],
        primary_test="tests/test_orders.py::test_create_order_after_two_adds",
        entry="app/orders.py::create_order",
        chain=["app/orders.py::create_order", "app/inventory.py::Stock.reserve",
               "app/inventory.py::Stock.add"],
        gold=["app/inventory.py::Stock.add"], gold_files=[I_],
        extra_deps=["app/inventory.py::Stock.available"],
        decoys=["app/inventory.py::Stock.reserve"],
        derivation=(
            "The test adds 2 then 3 units and reserves 5 through create_order. The edit makes "
            "add keep only the last quantity (3), so reserve raises 'insufficient stock' in "
            "Stock.reserve. The raising frame is reserve but the defect is add, which is called "
            "by the TEST, not by create_order: the link is shared state (self.items) with no call "
            "edge. Hard by construction; the only graph route is test coverage."
        ),
    ),
    # ------------------------------------------------------------------ C: 2-3 hops
    dict(
        id="C1", family="C", project="S",
        title="percentage divided by 10: three call hops below the entry",
        edits=[(M_, "amount * pct / 100", "amount * pct / 10")],
        primary_test="tests/test_orders.py::test_create_order",
        entry="app/orders.py::create_order",
        chain=["app/orders.py::create_order", "app/pricing.py::gross", "app/pricing.py::discount",
               "app/money.py::apply_pct"],
        gold=["app/money.py::apply_pct"], gold_files=[M_],
        extra_deps=["app/pricing.py::net_price", "app/pricing.py::tax", "app/money.py::round_money"],
        decoys=["app/pricing.py::tax", "app/pricing.py::net_price", "app/money.py::round_money"],
        derivation=(
            "create_order -> gross -> discount -> apply_pct (3 call hops). With pct=10 the edit "
            "makes apply_pct(200, 10) return 200 instead of 20, so discount returns 0 and the "
            "total is wrong. round_money, tax and net_price are unchanged."
        ),
    ),
    dict(
        id="C2", family="C", project="S",
        title="net_price adds instead of multiplies: two hops below the entry",
        edits=[(P_, "return round_money(price * qty)", "return round_money(price + qty)")],
        primary_test="tests/test_orders.py::test_quote",
        entry="app/orders.py::quote",
        chain=["app/orders.py::quote", "app/pricing.py::gross", "app/pricing.py::net_price"],
        gold=["app/pricing.py::net_price"], gold_files=[P_],
        extra_deps=["app/pricing.py::discount", "app/pricing.py::tax"],
        decoys=["app/pricing.py::discount", "app/pricing.py::tax"],
        derivation=(
            "quote -> gross -> net_price (2 hops). The edit computes 50 + 2 = 52 instead of 100 "
            "for the line total, so every later step is wrong. discount and tax are correct "
            "(their own tests pass)."
        ),
    ),
    dict(
        id="C3", family="C", project="L",
        title="rate lookup inverted: two hops below transfer",
        edits=[("app/rates.py", "return RATES[currency]", "return 1 / RATES[currency]")],
        primary_test="tests/test_transfer.py::test_transfer_converts",
        entry="app/transfer.py::transfer",
        chain=["app/transfer.py::transfer", "app/convert.py::convert", "app/rates.py::lookup"],
        gold=["app/rates.py::lookup"], gold_files=["app/rates.py"],
        extra_deps=["app/convert.py::convert"],
        decoys=["app/convert.py::convert", "app/accounts.py::Account.withdraw"],
        derivation=(
            "transfer -> convert -> lookup (2 hops). The edit returns 1/rate, so convert(100, "
            "USD, EUR) = 100 / 1.0 * (1/0.9) = 111.11 instead of 90. convert's formula is "
            "unchanged and correct; test_convert fails only because lookup is wrong."
        ),
    ),
    dict(
        id="C4", family="C", project="L",
        title="fee squared: three hops below Account.withdraw",
        edits=[("app/fees.py", "amount * settings.FEE_RATE, 2)", "amount * settings.FEE_RATE ** 2, 2)")],
        primary_test="tests/test_accounts.py::test_withdraw_cost",
        entry="app/accounts.py::Account.withdraw",
        chain=["app/accounts.py::Account.withdraw", "app/accounts.py::Account._debit",
               "app/fees.py::with_fee", "app/fees.py::fee"],
        gold=["app/fees.py::fee"], gold_files=["app/fees.py"],
        extra_deps=["app/fees.py::with_fee", "cfg:FEE_RATE"],
        decoys=["app/fees.py::with_fee", "app/accounts.py::Account._debit"],
        derivation=(
            "Account.withdraw -> _debit -> with_fee -> fee (3 hops). The edit makes fee(100) = "
            "0.01 (rate squared) so the withdrawn cost is 100.01 instead of 101. with_fee only "
            "adds fee to the amount and is correct."
        ),
    ),
    # ------------------------------------------------------------------ D: configuration
    dict(
        id="D1", family="D", project="S",
        title="compose sets the cache host to a typo (value error)",
        edits=[(CMP, "      CACHE_HOST: cache\n", "      CACHE_HOST: cahce\n")],
        primary_test="tests/test_cache.py::test_connect",
        entry="app/cache.py::connect",
        chain=["app/cache.py::connect", "cfg:CACHE_HOST"],
        gold=["cfg:CACHE_HOST"], gold_files=[CMP],
        extra_deps=["app/cache.py::Client.__init__"],
        decoys=["cfg:CACHE_PORT", "app/cache.py::Client.__init__"],
        derivation=(
            "conftest loads the compose api environment, so the host seen by settings.CACHE_HOST "
            "is the typo 'cahce'; Client.__init__ raises 'cannot reach host cahce'. The cause is "
            "the VALUE of key CACHE_HOST in compose.yaml. Values are not in the graph (no value "
            "flow in the MVP), so the expected answer is the key and its compose file."
        ),
    ),
    dict(
        id="D2", family="D", project="S",
        title="settings default port wrong and compose no longer sets it",
        edits=[(S_, 'os.getenv("CACHE_PORT", "6379")', 'os.getenv("CACHE_PORT", "6397")'),
               (CMP, '      CACHE_PORT: "6379"\n', "")],
        primary_test="tests/test_cache.py::test_connect",
        entry="app/cache.py::connect",
        chain=["app/cache.py::connect", "cfg:CACHE_PORT"],
        gold=["cfg:CACHE_PORT"], gold_files=[S_],
        extra_deps=["app/cache.py::Client.__init__"],
        decoys=["cfg:CACHE_HOST", "app/cache.py::Client.__init__"],
        derivation=(
            "compose no longer sets CACHE_PORT, so settings.py falls back to its default, which "
            "was changed to 6397 (transposed digits). Client.__init__ raises 'cannot reach host "
            "cache port 6397'. Cause: key CACHE_PORT (default in app/settings.py)."
        ),
    ),
    dict(
        id="D3", family="D", project="S",
        title="compose key renamed to CACHE_HOSTNAME, code reads CACHE_HOST (default localhost)",
        edits=[(S_, 'os.getenv("CACHE_HOST", "cache")', 'os.getenv("CACHE_HOST", "localhost")'),
               (CMP, "      CACHE_HOST: cache\n", "      CACHE_HOSTNAME: cache\n")],
        primary_test="tests/test_cache.py::test_connect",
        entry="app/cache.py::connect",
        chain=["app/cache.py::connect", "cfg:CACHE_HOST"],
        gold=["cfg:CACHE_HOST", "cfg:CACHE_HOSTNAME"], gold_files=[CMP, S_],
        extra_deps=["app/cache.py::Client.__init__"],
        decoys=["cfg:CACHE_PORT", "app/cache.py::Client.__init__"],
        derivation=(
            "The code reads CACHE_HOST (default now 'localhost'); compose sets CACHE_HOSTNAME, a "
            "name nothing reads. So the service connects to 'localhost' and fails. Either side "
            "of the name mismatch is an acceptable answer: cfg:CACHE_HOST (code) or "
            "cfg:CACHE_HOSTNAME (compose)."
        ),
    ),
    dict(
        id="D4", family="D", project="S",
        title="compose limits MAX_QTY to 1; order of 2 rejected",
        edits=[(CMP, '      TAX_RATE: "0.2"\n', '      TAX_RATE: "0.2"\n      MAX_QTY: "1"\n')],
        primary_test="tests/test_orders.py::test_create_order",
        entry="app/orders.py::create_order",
        chain=["app/orders.py::create_order", "app/inventory.py::Stock.reserve", "cfg:MAX_QTY"],
        gold=["cfg:MAX_QTY"], gold_files=[CMP],
        extra_deps=["app/inventory.py::Stock.reserve"],
        decoys=["app/inventory.py::Stock.reserve", "app/inventory.py::Stock.available",
                "cfg:CACHE_HOST"],
        derivation=(
            "reserve reads settings.MAX_QTY. compose now sets MAX_QTY=1 for the api service, so "
            "create_order(.., qty=2) raises 'qty above limit' in Stock.reserve. Stock.reserve is "
            "correct; the cause is the config value of key MAX_QTY in compose.yaml."
        ),
    ),
    # ------------------------------------------------------------------ F: patch breaks a dependant
    dict(
        id="F1", family="F", project="S",
        title="signature change: net_price gains a required parameter",
        edits=[(P_, "def net_price(price, qty):\n    return round_money(price * qty)",
                "def net_price(price, qty, unit_discount):\n"
                "    return round_money(price * qty - unit_discount)")],
        modified=["app/pricing.py::net_price"],
        expected_dependants=["app/pricing.py::gross", "app/orders.py::quote",
                             "app/orders.py::create_order"],
        expected_direct=["app/pricing.py::gross"],
        expected_flags=["signature_change_external_callers:app/pricing.py::net_price"],
        predicted_failing=[
            "tests/test_pricing.py::test_net_price", "tests/test_pricing.py::test_gross_plain",
            "tests/test_pricing.py::test_gross_with_discount", "tests/test_orders.py::test_quote",
            "tests/test_orders.py::test_create_order",
            "tests/test_orders.py::test_create_order_exact_stock",
            "tests/test_orders.py::test_create_order_after_two_adds"],
        derivation=(
            "net_price gains a mandatory third parameter. Callers: gross (pricing.py) passes two "
            "arguments -> TypeError. gross is called by quote and create_order (depth 2). "
            "Tests that reach net_price: test_net_price directly, gross tests, all orders tests. "
            "test_discount, test_tax, test_money and test_inventory/test_cache do not touch it."
        ),
    ),
    dict(
        id="F2", family="F", project="S",
        title="behaviour change: round_money truncates (many dependants, one failing test)",
        edits=[(M_, "return round(x + 1e-9, 2)", "return int(x * 100) / 100")],
        modified=["app/money.py::round_money"],
        expected_dependants=["app/money.py::apply_pct", "app/pricing.py::net_price",
                             "app/pricing.py::discount", "app/pricing.py::tax",
                             "app/pricing.py::gross", "app/orders.py::quote",
                             "app/orders.py::create_order"],
        expected_direct=["app/money.py::apply_pct", "app/pricing.py::net_price",
                         "app/pricing.py::discount", "app/pricing.py::tax", "app/pricing.py::gross"],
        expected_flags=[],
        predicted_failing=["tests/test_money.py::test_round_money"],
        derivation=(
            "round_money(1.005) now truncates to 1.0 instead of rounding to 1.01, so "
            "test_round_money fails. Dependants by reading the source: direct callers apply_pct, "
            "net_price, discount, tax, gross (all call round_money); depth 2: quote and "
            "create_order via gross. The other tests use values with at most 2 exact decimals so "
            "truncation equals rounding: predicted pass. Many dependants, one real failure: "
            "this case measures how much of the suite the tool selects for a benign-looking edit."
        ),
    ),
    dict(
        id="F3", family="F", project="L",
        title="rename: with_fee -> fee_inclusive, callers not updated (import-time break)",
        edits=[("app/fees.py", "def with_fee(amount):", "def fee_inclusive(amount):")],
        modified=["app/fees.py::with_fee"],
        expected_dependants=["app/accounts.py::Account._debit", "app/accounts.py::Account.withdraw",
                             "app/accounts.py::SavingsAccount.withdraw", "app/transfer.py::transfer"],
        expected_direct=["app/accounts.py::Account._debit"],
        expected_flags=["removed_symbol_still_referenced:app/fees.py::with_fee",
                        "import_time_break:app/fees.py::with_fee"],
        predicted_failing=[
            "tests/test_fees.py::test_fee", "tests/test_fees.py::test_with_fee",
            "tests/test_accounts.py::test_deposit", "tests/test_accounts.py::test_withdraw_cost",
            "tests/test_accounts.py::test_savings_withdraw",
            "tests/test_accounts.py::test_savings_limit",
            "tests/test_transfer.py::test_transfer_converts", "tests/test_report.py::test_total_usd"],
        derivation=(
            "with_fee no longer exists. accounts.py does `from app.fees import with_fee`, so "
            "importing app.accounts raises ImportError. Direct caller: Account._debit; depth 2: "
            "Account.withdraw and SavingsAccount.withdraw (both call _debit); depth 3: transfer, which "
            "calls src.withdraw on an untyped parameter (a real dependant reachable by name only). "
            "test_fees.py also "
            "imports with_fee (collection error), test_accounts/test_transfer/test_report import "
            "app.accounts (import-time failure) even where the test does not call with_fee: "
            "8 of 11 visible tests are predicted to fail; test_rates and test_convert (2 + 1 = 3) "
            "do not import fees or accounts."
        ),
    ),
    dict(
        id="F4", family="F", project="S",
        title="config value change: compose TAX_RATE 0.2 -> 0.25",
        edits=[(CMP, '      TAX_RATE: "0.2"\n', '      TAX_RATE: "0.25"\n')],
        modified=["cfg:TAX_RATE"],
        expected_dependants=["app/pricing.py::tax", "app/pricing.py::gross", "app/orders.py::quote",
                             "app/orders.py::create_order"],
        expected_direct=["app/pricing.py::tax"],
        expected_flags=["config_default_changed:cfg:TAX_RATE"],
        predicted_failing=[
            "tests/test_pricing.py::test_tax", "tests/test_pricing.py::test_gross_plain",
            "tests/test_pricing.py::test_gross_with_discount", "tests/test_orders.py::test_quote",
            "tests/test_orders.py::test_create_order",
            "tests/test_orders.py::test_create_order_exact_stock",
            "tests/test_orders.py::test_create_order_after_two_adds"],
        derivation=(
            "conftest loads compose env into the process, so the new rate reaches settings. "
            "Reader of TAX_RATE: tax (reads settings.TAX_RATE); depth 2: gross; depth 3: quote "
            "and create_order. Every test asserting a taxed total fails (7); net_price, "
            "discount, money and inventory/cache tests do not use tax."
        ),
    ),
    dict(
        id="F5", family="F", project="L",
        title="base-class signature change with an overriding subclass and untyped callers",
        edits=[("app/accounts.py",
                "    def withdraw(self, amount):\n        return self._debit(amount)\n\n\n"
                "class SavingsAccount(Account):",
                "    def withdraw(self, amount, memo):\n        return self._debit(amount)\n\n\n"
                "class SavingsAccount(Account):")],
        modified=["app/accounts.py::Account.withdraw"],
        expected_dependants=["app/accounts.py::SavingsAccount.withdraw", "app/transfer.py::transfer"],
        expected_direct=["app/accounts.py::SavingsAccount.withdraw", "app/transfer.py::transfer"],
        expected_flags=["signature_change_overriders:app/accounts.py::Account.withdraw",
                        "signature_change_external_callers:app/accounts.py::Account.withdraw"],
        predicted_failing=["tests/test_accounts.py::test_withdraw_cost",
                           "tests/test_transfer.py::test_transfer_converts"],
        derivation=(
            "Account.withdraw gains a required `memo`. SavingsAccount.withdraw overrides it with "
            "the old signature (so savings tests still pass) -> overrider, listed structurally. "
            "Callers: test_withdraw_cost calls Account.withdraw(100) directly -> TypeError; "
            "transfer calls src.withdraw(amount) on an untyped parameter -> TypeError for the "
            "Account in test_transfer (reachable only by method name). Predicted failures: those "
            "two tests."
        ),
    ),
    # ------------------------------------------------------------------ G: misleading relationships
    dict(
        id="G1", family="G", project="S",
        title="hub decoy: normalize() has 15 callers; bug is in parse_qty",
        edits=[
            ("app/util.py", None, "def normalize(text):\n    return text.strip().lower()\n"),
            ("app/validate.py", None,
             "from app.util import normalize\n\n\ndef parse_qty(text):\n"
             "    return int(normalize(text)) + 1\n"),
            ("app/tags.py", None, _TAGS),
            (O_, "from app.pricing import gross\n",
             "from app.pricing import gross\nfrom app.validate import parse_qty\n"),
            (O_, "    return total\n",
             "    return total\n\n\ndef create_order_from_text(stock, sku, price, qty_text):\n"
             "    return create_order(stock, sku, price, parse_qty(qty_text))\n"),
            ("tests/test_text_orders.py", None,
             "from app.inventory import Stock\nfrom app.orders import create_order_from_text\n\n\n"
             "def test_order_from_text():\n    s = Stock()\n    s.add(\"A\", 10)\n"
             "    assert create_order_from_text(s, \"A\", 100, \" 2 \") == 240.0\n"),
        ],
        primary_test="tests/test_text_orders.py::test_order_from_text",
        entry="app/orders.py::create_order_from_text",
        chain=["app/orders.py::create_order_from_text", "app/validate.py::parse_qty"],
        gold=["app/validate.py::parse_qty"], gold_files=["app/validate.py"],
        extra_deps=["app/orders.py::create_order"],
        decoys=["app/util.py::normalize", "app/tags.py::tag_00", "app/tags.py::tag_07"],
        derivation=(
            "create_order_from_text(..., ' 2 ') should order 2 units (240.0). parse_qty adds 1, "
            "ordering 3 (360.0). parse_qty is one call hop below the entry. normalize is a "
            "shared helper called by parse_qty and 14 unrelated tag_NN functions (a hub): it is "
            "correct (strip/lower), and the tag functions are unrelated to the failure."
        ),
    ),
    dict(
        id="G2", family="G", project="S",
        title="name collision: two compute_total functions, the failing one is billing's",
        edits=[
            ("app/billing/__init__.py", None, ""),
            ("app/billing/totals.py", None,
             "def compute_total(items):\n"
             "    return sum(i[\"prize\"] * i[\"qty\"] for i in items)\n"),
            ("app/reports/__init__.py", None, ""),
            ("app/reports/totals.py", None,
             "def compute_total(rows):\n    return sum(r[\"amount\"] for r in rows)\n"),
            ("app/reports/summary.py", None,
             "from app.reports.totals import compute_total\n\n\n"
             "def daily_summary(rows):\n    return {\"total\": compute_total(rows)}\n"),
            ("app/invoice.py", None,
             "from app.billing.totals import compute_total\n\n\n"
             "def create_invoice(items):\n    return compute_total(items)\n"),
            ("tests/test_invoice.py", None,
             "from app.invoice import create_invoice\n\n\ndef test_invoice_total():\n"
             "    assert create_invoice([{\"price\": 10, \"qty\": 3}]) == 30\n"),
            ("tests/test_reports.py", None,
             "from app.reports.summary import daily_summary\n\n\ndef test_daily_summary():\n"
             "    assert daily_summary([{\"amount\": 5}, {\"amount\": 7}]) == {\"total\": 12}\n"),
        ],
        primary_test="tests/test_invoice.py::test_invoice_total",
        entry="app/invoice.py::create_invoice",
        chain=["app/invoice.py::create_invoice", "app/billing/totals.py::compute_total"],
        gold=["app/billing/totals.py::compute_total"], gold_files=["app/billing/totals.py"],
        extra_deps=[],
        decoys=["app/reports/totals.py::compute_total", "app/reports/summary.py::daily_summary"],
        derivation=(
            "create_invoice imports compute_total from app.billing.totals; its body reads the "
            "misspelled key 'prize' -> KeyError. app.reports.totals defines a SAME-NAMED "
            "compute_total that is correct, exercised only by test_daily_summary (passing) and "
            "unrelated to the invoice path. A name-based search cannot tell them apart; the "
            "import resolves it."
        ),
    ),
    # ------------------------------------------------------------------ H: static-analysis blind
    dict(
        id="H1", family="H", project="S",
        title="dictionary dispatch hides the failing handler",
        edits=[
            ("app/handlers.py", None,
             "def _paid(order):\n    return order[\"total\"]\n\n\n"
             "def _refund(order):\n    return order[\"total\"]\n\n\n"
             "HANDLERS = {\"paid\": _paid, \"refund\": _refund}\n\n\n"
             "def handle(event):\n    return HANDLERS[event[\"kind\"]](event[\"order\"])\n"),
            ("tests/test_handlers.py", None,
             "from app.handlers import handle\n\n\ndef test_refund():\n"
             "    assert handle({\"kind\": \"refund\", \"order\": {\"total\": 10}}) == -10\n"),
        ],
        primary_test="tests/test_handlers.py::test_refund",
        entry="app/handlers.py::handle",
        chain=["app/handlers.py::handle", "app/handlers.py::_refund"],
        gold=["app/handlers.py::_refund"], gold_files=["app/handlers.py"],
        extra_deps=[], decoys=["app/handlers.py::_paid"], abstain_expected=True,
        derivation=(
            "handle() calls HANDLERS[event['kind']](...): a call through a subscript, so no "
            "static edge to _refund or _paid exists. _refund returns +total instead of -total. "
            "Expected tool behaviour: report the unresolved dynamic call site next to the symptom "
            "and abstain, not guess a confident cause."
        ),
    ),
    dict(
        id="H2", family="H", project="S",
        title="importlib plugin loaded by a built string",
        edits=[
            ("app/plugins.py", None,
             "import importlib\n\n\ndef run(name, value):\n"
             "    module = importlib.import_module(f\"app.plugin_{name}\")\n"
             "    return module.apply(value)\n"),
            ("app/plugin_double.py", None, "def apply(value):\n    return value * 3\n"),
            ("tests/test_plugins.py", None,
             "from app.plugins import run\n\n\ndef test_double_plugin():\n"
             "    assert run(\"double\", 4) == 8\n"),
        ],
        primary_test="tests/test_plugins.py::test_double_plugin",
        entry="app/plugins.py::run",
        chain=["app/plugins.py::run", "app/plugin_double.py::apply"],
        gold=["app/plugin_double.py::apply"], gold_files=["app/plugin_double.py"],
        extra_deps=[], decoys=[], abstain_expected=True,
        derivation=(
            "run() imports app.plugin_<name> by a string built at runtime and calls its apply: "
            "no import or call edge exists in the source. plugin_double.apply multiplies by 3 "
            "instead of 2. Expected tool behaviour: flag the dynamic import as unknown and abstain."
        ),
    ),
]

FAMILY_COUNTS = {"A": 2, "B": 4, "C": 4, "D": 4, "F": 5, "G": 2, "H": 2}
