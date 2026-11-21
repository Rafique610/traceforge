# Quality gates (a task closes only when its relevant gates pass)

- **Requirements:** step-doc acceptance criteria listed, each mapped to a test or command.
- **Architecture:** feature folder, files <300 lines, contracts untouched or changed by their own PR.
- **Implementation:** no placeholders or fake success paths; ORM only; env only via Settings.
- **Testing:** targeted tests pass; error paths covered; `ruff check` + `ruff format --check` pass; counts come from real runs.
- **Security:** no secrets in code/logs; LLM tools typed and validated; hidden tests never in prompts; patches policy-checked; nothing deployed.
- **Documentation:** README, step doc, checklist, encyclopedia updated.
- **Integration:** consumers work against samples or the real producer; migration applies.
- **Research validity:** four conditions, 3 attempts, temperature 0, pinned model, results from saved runs, negatives kept.
- **Final delivery:** full suite, clean-tree report, no commits without approval.
