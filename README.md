# SSI Sats Monorepo

## Build the example firmware

```bash
bazel build --config=pico //:blink
```

## Run the tests

```bash
bazel test --test_output=all //test:example_test
```

## Run the CI checks locally

```bash
bazel test //test:example_test --test_output=errors
bazel build --config=pico //:blink
```

## Run Python tools

```bash
uv run scripts/parse_slate.py bazel-bin/blink Slate
```
