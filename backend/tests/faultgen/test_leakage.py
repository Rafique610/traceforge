from traceforge.faultgen.leakage import gold_terms, input_literals, scan_visible, shared_inputs


def test_seed_visible_files_are_clean(builts):
    for b in builts:
        terms = gold_terms(b.manifest, dict(b.draft.edits), b.draft.runtime)
        assert scan_visible(b.draft.reproducer_files, terms) == [], b.manifest.case_id


def test_scan_flags_gold_names_and_banned_words():
    text = "# the bug is in order_headline\nx = REDIS_HOST\n"
    assert len(scan_visible({"t.py": text}, {"order_headline", "REDIS_HOST"})) == 3


def test_shared_input_literals_are_detected_but_expected_values_are_not():
    vis = {
        "test_a.py": 'def test_x():\n    f("buyer@example.com", 4.5)\n    assert g() == "0.00"\n'
    }
    hid_same = {"test_b.py": 'def test_y():\n    f("buyer@example.com")\n'}
    hid_other = {"test_b.py": 'def test_y():\n    f("other@shop.test")\n    assert g() == "0.00"\n'}
    assert shared_inputs(vis, hid_same) == ["buyer@example.com"]
    assert shared_inputs(vis, hid_other) == []
    assert input_literals("x = {'customer_email': 'a'}") == set()


def test_seed_hidden_inputs_differ_from_visible(builts):
    for b in builts:
        if b.draft.hidden_files:
            shared = set(shared_inputs(b.draft.reproducer_files, b.draft.hidden_files))
            assert shared <= set(b.draft.allowed_shared), b.manifest.case_id
