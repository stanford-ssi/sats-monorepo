## How to build an app

``` bash
bazel build --config=pico //:blink
```


## How to run a test case
``` bash
bazel test --cxxopt=-std=c++17 --test_output=all //test:example_test
```

## How to run scripts using uv
``` bash
uv run scripts/parse_slate.py bazel-bin/blink Slate
```
