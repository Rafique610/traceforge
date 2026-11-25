# Derivations of expected relationships (hand-written)
Written from the template source and the stated edit, before any tool run. Second reviewer: verify each row of `expected_relationships.csv` against these notes and the committed trees, and fill `reviewer_verdict` (ok / wrong / unclear).

## A1 (family A, project S): sign error inside the function the failing test calls

test_discount calls discount(200, 10) directly and expects 180. The edited body adds the percentage (220), so the defect is the sign in discount itself. apply_pct and round_money are unchanged and covered by passing tests in test_money.py.

## A2 (family A, project S): tax doubled; symptom entry gross and cause tax live in the same file

test_gross_plain calls gross(100, 1) and expects 120 = 100 + 20 tax. gross calls tax (same file). The edit doubles the tax so gross returns 140. net_price and discount are untouched and give 100 for these arguments.

## B1 (family B, project S): gross drops the tax; failing test enters through orders.quote

test_quote calls orders.quote(50, 2, 10) expecting 108 (net 100, 10% off = 90, tax 18). quote only forwards to pricing.gross (other file, one call hop). The edit makes gross return the pre-tax 90. tax itself is correct (test_tax passes).

## B2 (family B, project S): off-by-one in Stock.reserve; test enters through orders.create_order

The test reserves exactly the stock (3 of 3). create_order calls stock.reserve (another file, one hop; the receiver is a parameter so the static edge is only name-resolved). The edit turns > into >=, so reserving all stock raises ValueError 'insufficient stock'. Stock.available and Stock.add are correct.

## B3 (family B, project L): currency conversion inverted; test enters through transfer.transfer

transfer(a, b, 100) USD->EUR must return 90 (100 / 1.0 * 0.9). transfer calls convert (other file, one hop). The edit computes 100 * 1.0 / 0.9 = 111.11. lookup returns the correct rate (test_lookup passes) and withdraw/deposit are not involved in the returned value.

## B4 (family B, project S): Stock.add overwrites instead of accumulating (state written by the test)

The test adds 2 then 3 units and reserves 5 through create_order. The edit makes add keep only the last quantity (3), so reserve raises 'insufficient stock' in Stock.reserve. The raising frame is reserve but the defect is add, which is called by the TEST, not by create_order: the link is shared state (self.items) with no call edge. Hard by construction; the only graph route is test coverage.

## C1 (family C, project S): percentage divided by 10: three call hops below the entry

create_order -> gross -> discount -> apply_pct (3 call hops). With pct=10 the edit makes apply_pct(200, 10) return 200 instead of 20, so discount returns 0 and the total is wrong. round_money, tax and net_price are unchanged.

## C2 (family C, project S): net_price adds instead of multiplies: two hops below the entry

quote -> gross -> net_price (2 hops). The edit computes 50 + 2 = 52 instead of 100 for the line total, so every later step is wrong. discount and tax are correct (their own tests pass).

## C3 (family C, project L): rate lookup inverted: two hops below transfer

transfer -> convert -> lookup (2 hops). The edit returns 1/rate, so convert(100, USD, EUR) = 100 / 1.0 * (1/0.9) = 111.11 instead of 90. convert's formula is unchanged and correct; test_convert fails only because lookup is wrong.

## C4 (family C, project L): fee squared: three hops below Account.withdraw

Account.withdraw -> _debit -> with_fee -> fee (3 hops). The edit makes fee(100) = 0.01 (rate squared) so the withdrawn cost is 100.01 instead of 101. with_fee only adds fee to the amount and is correct.

## D1 (family D, project S): compose sets the cache host to a typo (value error)

conftest loads the compose api environment, so the host seen by settings.CACHE_HOST is the typo 'cahce'; Client.__init__ raises 'cannot reach host cahce'. The cause is the VALUE of key CACHE_HOST in compose.yaml. Values are not in the graph (no value flow in the MVP), so the expected answer is the key and its compose file.

## D2 (family D, project S): settings default port wrong and compose no longer sets it

compose no longer sets CACHE_PORT, so settings.py falls back to its default, which was changed to 6397 (transposed digits). Client.__init__ raises 'cannot reach host cache port 6397'. Cause: key CACHE_PORT (default in app/settings.py).

## D3 (family D, project S): compose key renamed to CACHE_HOSTNAME, code reads CACHE_HOST (default localhost)

The code reads CACHE_HOST (default now 'localhost'); compose sets CACHE_HOSTNAME, a name nothing reads. So the service connects to 'localhost' and fails. Either side of the name mismatch is an acceptable answer: cfg:CACHE_HOST (code) or cfg:CACHE_HOSTNAME (compose).

## D4 (family D, project S): compose limits MAX_QTY to 1; order of 2 rejected

reserve reads settings.MAX_QTY. compose now sets MAX_QTY=1 for the api service, so create_order(.., qty=2) raises 'qty above limit' in Stock.reserve. Stock.reserve is correct; the cause is the config value of key MAX_QTY in compose.yaml.

## F1 (family F, project S): signature change: net_price gains a required parameter

net_price gains a mandatory third parameter. Callers: gross (pricing.py) passes two arguments -> TypeError. gross is called by quote and create_order (depth 2). Tests that reach net_price: test_net_price directly, gross tests, all orders tests. test_discount, test_tax, test_money and test_inventory/test_cache do not touch it.

## F2 (family F, project S): behaviour change: round_money truncates (many dependants, one failing test)

round_money(1.005) now truncates to 1.0 instead of rounding to 1.01, so test_round_money fails. Dependants by reading the source: direct callers apply_pct, net_price, discount, tax, gross (all call round_money); depth 2: quote and create_order via gross. The other tests use values with at most 2 exact decimals so truncation equals rounding: predicted pass. Many dependants, one real failure: this case measures how much of the suite the tool selects for a benign-looking edit.

## F3 (family F, project L): rename: with_fee -> fee_inclusive, callers not updated (import-time break)

with_fee no longer exists. accounts.py does `from app.fees import with_fee`, so importing app.accounts raises ImportError. Direct caller: Account._debit; depth 2: Account.withdraw and SavingsAccount.withdraw (both call _debit); depth 3: transfer, which calls src.withdraw on an untyped parameter (a real dependant reachable by name only). test_fees.py also imports with_fee (collection error), test_accounts/test_transfer/test_report import app.accounts (import-time failure) even where the test does not call with_fee: 8 of 11 visible tests are predicted to fail; test_rates and test_convert (2 + 1 = 3) do not import fees or accounts.

## F4 (family F, project S): config value change: compose TAX_RATE 0.2 -> 0.25

conftest loads compose env into the process, so the new rate reaches settings. Reader of TAX_RATE: tax (reads settings.TAX_RATE); depth 2: gross; depth 3: quote and create_order. Every test asserting a taxed total fails (7); net_price, discount, money and inventory/cache tests do not use tax.

## F5 (family F, project L): base-class signature change with an overriding subclass and untyped callers

Account.withdraw gains a required `memo`. SavingsAccount.withdraw overrides it with the old signature (so savings tests still pass) -> overrider, listed structurally. Callers: test_withdraw_cost calls Account.withdraw(100) directly -> TypeError; transfer calls src.withdraw(amount) on an untyped parameter -> TypeError for the Account in test_transfer (reachable only by method name). Predicted failures: those two tests.

## G1 (family G, project S): hub decoy: normalize() has 15 callers; bug is in parse_qty

create_order_from_text(..., ' 2 ') should order 2 units (240.0). parse_qty adds 1, ordering 3 (360.0). parse_qty is one call hop below the entry. normalize is a shared helper called by parse_qty and 14 unrelated tag_NN functions (a hub): it is correct (strip/lower), and the tag functions are unrelated to the failure.

## G2 (family G, project S): name collision: two compute_total functions, the failing one is billing's

create_invoice imports compute_total from app.billing.totals; its body reads the misspelled key 'prize' -> KeyError. app.reports.totals defines a SAME-NAMED compute_total that is correct, exercised only by test_daily_summary (passing) and unrelated to the invoice path. A name-based search cannot tell them apart; the import resolves it.

## H1 (family H, project S): dictionary dispatch hides the failing handler

handle() calls HANDLERS[event['kind']](...): a call through a subscript, so no static edge to _refund or _paid exists. _refund returns +total instead of -total. Expected tool behaviour: report the unresolved dynamic call site next to the symptom and abstain, not guess a confident cause.

## H2 (family H, project S): importlib plugin loaded by a built string

run() imports app.plugin_<name> by a string built at runtime and calls its apply: no import or call edge exists in the source. plugin_double.apply multiplies by 3 instead of 2. Expected tool behaviour: flag the dynamic import as unknown and abstain.
