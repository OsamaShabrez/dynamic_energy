# Dynamic Energy Monitor validation tests

These tests validate the ranking, accounting, and generated sensor
behavior with isolated in-memory fakes. They do not modify the real
persistent storage.

## Files

- `conftest.py`
- `test_ranking.py`
- `test_accounting.py`
- `test_sensors.py`

## Install

Place the `tests` directory at the root of the custom integration repository,
next to `custom_components`.

## Run

```bash
pytest -q tests
```

Run individual suites:

```bash
pytest -q tests/test_ranking.py
pytest -q tests/test_accounting.py
pytest -q tests/test_sensors.py
```

The tests import the current `custom_components.dynamic_energy` package, so the
integration itself must be syntactically valid before pytest can import it.
