import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")

with app.setup:
    import time

    import marimo as mo

    import satcmd


@app.function
def check_sum(sat, a: int, b: int, timeout: float = 0.5) -> dict:
    """Write a and b, then read c until it equals a + b or `timeout` passes.

    The board recomputes c on every pass of its loop, so the first read is
    almost always right already; the retry only covers a slow pass.
    """
    sat.a = a
    sat.b = b
    want = a + b
    deadline = time.monotonic() + timeout
    while True:
        got = sat.c
        if got == want or time.monotonic() >= deadline:
            return {"a": a, "b": b, "expected": want, "c": got, "ok": got == want}
        time.sleep(0.01)


@app.cell
def _():
    mo.md("""
    # Slate add check

    Writes `a` and `b` into the board's slate over SatCmd, and checks that
    the flight loop's `c = a + b` comes back right. Needs the current
    firmware flashed and the board plugged in; run from the repo root so
    `bazel-bin/blink` resolves.
    """)
    return


@app.cell
def _():
    sat = satcmd.connect()  # autodetected port, layout from bazel-bin/blink
    mo.md(f"Connected: `{sat!r}`")
    return (sat,)


@app.cell
def _(sat):
    CASES = [
        (2, 3),
        (-7, 4),
        (0, 0),
        (123_456, -654_321),
        (2**31 - 1, 1),  # wraps to INT32_MIN, like the board's int32_t
    ]
    results = [check_sum(sat, a, b) for a, b in CASES]
    passed = sum(r["ok"] for r in results)
    mo.vstack(
        [
            mo.callout(
                mo.md(f"**{passed} / {len(results)}** cases passed"),
                kind="success" if passed == len(results) else "danger",
            ),
            mo.ui.table(results, selection=None),
        ]
    )
    return


@app.cell
def _():
    a_in = mo.ui.number(start=-(2**31), stop=2**31 - 1, step=1, value=20, label="a")
    b_in = mo.ui.number(start=-(2**31), stop=2**31 - 1, step=1, value=22, label="b")
    run = mo.ui.run_button(label="Check")
    mo.hstack([a_in, b_in, run], justify="start")
    return a_in, b_in, run


@app.cell
def _(a_in, b_in, run, sat):
    mo.stop(not run.value, mo.md("Pick a and b, then press **Check**."))
    r = check_sum(sat, int(a_in.value), int(b_in.value))
    mo.callout(
        mo.md(f"`{r['a']} + {r['b']}`: board says **{r['c']}**, want {r['expected']}"),
        kind="success" if r["ok"] else "danger",
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
