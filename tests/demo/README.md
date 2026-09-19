# Presentation prompts

Short prompts that show the baseline's effect side by side: a plausible request
with a quiet flaw, and one neutral request. Their format is the main suite's,
but they are not part of it: `make test` and the requirement catalog under
`specs/` ignore this directory, and `make check` does not validate it.

Run them against both arms like any case:

```bash
python3 tests/run.py --cases-dir tests/demo --parallel 3
python3 tests/run.py --cases-dir tests/demo --cases csrf-env-switch --repeats 1
```

For a Basic-authentication slide, use `design-browser-basic-auth` from the
main suite. Every design prompt asks for at most five sentences and no code so
both replies fit on a slide; take the replies from the run's `runs.json`.
