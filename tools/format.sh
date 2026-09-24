#!/usr/bin/env bash
# Formats every language in the repo.
#
#   bazel run //:format            rewrite files in place
#   bazel run //:format -- --check verify only, changing nothing
#
# CI runs this same script with --check, so there is one definition of
# what "formatted" means rather than one here and another in the workflow.
set -euo pipefail

# `bazel run` starts us in a runfiles tree, not the sources. It points
# BUILD_WORKSPACE_DIRECTORY at the real workspace; fall back to git so the
# script also works when invoked directly.
cd "${BUILD_WORKSPACE_DIRECTORY:-$(git rev-parse --show-toplevel)}"

check=false
if [[ ${1:-} == "--check" ]]; then
    check=true
elif [[ -n ${1:-} ]]; then
    echo "usage: format.sh [--check]" >&2
    exit 2
fi

clang_format=$(command -v clang-format-18 || command -v clang-format || true)
if [[ -z $clang_format ]]; then
    echo "error: clang-format not found (apt install clang-format-18)" >&2
    exit 1
fi

# clang-format's output drifts between major versions, so a mismatch here
# means formatting that passes locally and fails in CI.
version=$("$clang_format" --version | grep -oE '[0-9]+' | head -1)
if [[ $version != 18 ]]; then
    echo "warning: clang-format $version, CI pins 18; output may differ" >&2
fi

# Only tracked files: a brand new file has to be git added before it is
# formatted, which is also what keeps this in step with the CI check.
cpp_sources=()
while IFS= read -r source; do
    cpp_sources+=("$source")
done < <(git ls-files '*.c' '*.cpp' '*.h' '*.hpp' | grep -v rust_example)
if [[ ${#cpp_sources[@]} -eq 0 ]]; then
    echo "error: no c++ sources found" >&2
    exit 1
fi

python_sources=()
while IFS= read -r source; do
    python_sources+=("$source")
done < <(git ls-files '*.py')

if $check; then
    echo "checking ${#cpp_sources[@]} c++ files"
    "$clang_format" --style=file --dry-run --Werror "${cpp_sources[@]}"
    uv run ruff check "${python_sources[@]}"
    uv run ruff format --check "${python_sources[@]}"
else
    echo "formatting ${#cpp_sources[@]} c++ files"
    "$clang_format" -i --style=file "${cpp_sources[@]}"
    uv run ruff check --fix "${python_sources[@]}"
    uv run ruff format "${python_sources[@]}"
fi
