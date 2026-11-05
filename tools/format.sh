#!/usr/bin/env bash
# Formats every language in the repo.
#
#   bazelisk run //:format            rewrite files in place
#   bazelisk run //:format -- --check verify only, changing nothing
#
# CI runs this same script with --check, so there is one definition of
# what "formatted" means rather than one here and another in the workflow.
set -euo pipefail

# `bazelisk run` starts us in a runfiles tree, not the sources. It points
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

# clang-format comes from the uv dev group, pinned to an exact release:
# even patch releases within 18.x format some code differently, so a
# system install would pass locally and fail in CI (or the reverse).
clang_format=(uv run clang-format)

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
    "${clang_format[@]}" --style=file --dry-run --Werror "${cpp_sources[@]}"
    uv run ruff check "${python_sources[@]}"
    uv run ruff format --check "${python_sources[@]}"
else
    echo "formatting ${#cpp_sources[@]} c++ files"
    "${clang_format[@]}" -i --style=file "${cpp_sources[@]}"
    uv run ruff check --fix "${python_sources[@]}"
    uv run ruff format "${python_sources[@]}"
fi
