"""
cli.py - `satcmd`, a thin shell over satcmd.connect().

    uv run satcmd                         # the interactive browser
    uv run satcmd list                    # the fields the elf describes
    uv run satcmd read                    # every field, once
    uv run satcmd read sleep_ms board_power.voltage
    uv run satcmd write sleep_ms=500 led_enabled=false
    uv run satcmd --fake                  # any of the above, no board needed
"""

import argparse
import logging
import sys

from satcmd import layout
from satcmd.layout import Layout
from satcmd.link import SatError
from satcmd.sat import DEFAULT_ELF, DEFAULT_STRUCT, Sat, connect, resolve_elf


def print_layout(lay: Layout) -> None:
    print(f"struct {lay.name}  /* {lay.size} bytes */")
    for f in lay.fields:
        print(f"  {f.name:<28} offset {f.offset:>4}  width {f.width}  {f.type_name}")
    for name, why in lay.skipped.items():
        print(f"  {name:<28} skipped: {why}")


def cmd_read(sat: Sat, args) -> None:
    names = args.names or [f.name for f in sat.layout.fields]
    for name in names:
        field = sat.layout[name]
        print(f"{name:<28} {field.format(sat.read(name))}")


def cmd_write(sat: Sat, args) -> None:
    for assignment in args.assignments:
        name, sep, text = assignment.partition("=")
        if not sep:
            raise ValueError(f"expected FIELD=VALUE, got {assignment!r}")
        field = sat.layout[name]
        landed = sat.write(name, field.parse(text))
        print(f"{name:<28} {field.format(landed)}")


def cmd_tui(sat: Sat, args) -> None:
    from satcmd.tui import App, main
    from satcmd.tui.theme import Theme

    where = "fake board" if args.fake else repr(sat.link.transport)
    main(App(sat, theme=Theme.detect(), subtitle=where))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="satcmd", description="Read and write a board's slate by name."
    )
    parser.add_argument("--elf", default=DEFAULT_ELF, help=f"default {DEFAULT_ELF}")
    parser.add_argument("--struct", default=DEFAULT_STRUCT, help="default %(default)s")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--port", help="serial port (autodetected if omitted)")
    where.add_argument("--fake", action="store_true", help="use an in process board")
    parser.add_argument("--timeout", type=float, default=0.3, help="seconds per reply")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every frame")
    parser.set_defaults(run=cmd_tui)

    sub = parser.add_subparsers(title="commands")
    sub.add_parser("tui", help="interactive browser (the default)").set_defaults(
        run=cmd_tui
    )
    sub.add_parser("list", help="print the fields and exit").set_defaults(run=None)
    p = sub.add_parser("read", help="read fields (all of them by default)")
    p.add_argument("names", nargs="*", metavar="FIELD")
    p.set_defaults(run=cmd_read)
    p = sub.add_parser("write", help="write fields")
    p.add_argument("assignments", nargs="+", metavar="FIELD=VALUE")
    p.set_defaults(run=cmd_write)

    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    try:
        if args.run is None:  # list needs only the elf, not a board
            print_layout(layout.load(resolve_elf(args.elf), args.struct))
            return
        sat = connect(
            args.port,
            elf=args.elf,
            struct=args.struct,
            fake=args.fake,
            timeout=args.timeout,
        )
    except (OSError, ValueError, SatError) as err:
        sys.exit(f"error: {err}")
    with sat:
        try:
            args.run(sat, args)
        except (KeyError, ValueError, TypeError, SatError) as err:
            # KeyError reprs its message in quotes; the others read as is.
            sys.exit(f"error: {err.args[0] if err.args else err}")


if __name__ == "__main__":
    main()
