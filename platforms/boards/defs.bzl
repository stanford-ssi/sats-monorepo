"""Helpers for board-specific targets."""

# target_compatible_with for anything that is a complete firmware image:
# building one for a bare chip (or the host) is an error, and `//...`
# skips it.
REQUIRES_BOARD = select({
    "//platforms/boards:none": ["@platforms//:incompatible"],
    "//conditions:default": [],
})
