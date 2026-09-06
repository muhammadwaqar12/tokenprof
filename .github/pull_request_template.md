**What this changes**

**Why**

---

- [ ] `pytest -q` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] Added the test that would fail without this change

**If this adds an adapter**

- [ ] `matches` is exclusive (the detection test asserts exactly one adapter claims a payload)
- [ ] Segments carry names, so the per-tool breakdown stays useful
- [ ] Added a fixture under `tests/fixtures/`
