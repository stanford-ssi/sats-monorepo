"""
sat.py - a board's slate, as a python object.

    import satcmd

    with satcmd.connect() as sat:          # autodetected port, bazel-bin/blink
        sat.sleep_ms = 500
        assert sat.sleep_ms == 500
        print(sat.board_power.voltage)
        sat["board_power.current"]         # dotted names work as keys too

Every attribute read is a round trip to the board and every assignment is a
write the board confirms, so what you see is what the board holds.
"""

import os
import subprocess

from satcmd import layout as layout_mod
from satcmd.layout import Field, Layout
from satcmd.link import (
    DEFAULT_TIMEOUT,
    Link,
    SatError,
    SerialTransport,
    autodetect_port,
)
from satcmd.memory import FakeBoard

DEFAULT_ELF = "bazel-bin/blink"
DEFAULT_STRUCT = "Slate"


class Sat:
    """Read and write slate fields by name.

    Fields are attributes (`sat.sleep_ms`), nested structs are attribute
    chains (`sat.board_power.voltage`) and array elements are indexed
    (`sat.samples[3]`). Anything a method name would shadow is still
    reachable as `sat["name"]`.
    """

    def __init__(self, link: Link, layout: Layout):
        self._link = link
        self._layout = layout

    # -- by name -------------------------------------------------------

    @property
    def layout(self) -> Layout:
        return self._layout

    @property
    def link(self) -> Link:
        return self._link

    def read(self, name: str):
        """The current value of a field."""
        f = self._layout[name]
        return f.decode(self._call(f, self._link.read, f.offset, f.width))

    def write(self, name: str, value):
        """Write a field and return the value the board confirms it holds."""
        f = self._layout[name]
        raw = f.encode(value)
        return f.decode(self._call(f, self._link.write, f.offset, f.width, raw))

    def dump(self, prefix: str = "") -> dict:
        """Every field (under `prefix`, if given) read fresh, by name."""
        return {f.name: self.read(f.name) for f in self._fields_under(prefix)}

    def __getitem__(self, name: str):
        return self.read(name)

    def __setitem__(self, name: str, value) -> None:
        self.write(name, value)

    # -- by attribute --------------------------------------------------

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)  # keeps copy/pickle from probing the board
        return self._resolve(name)

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        elif name in self._layout:
            self.write(name, value)
        elif self._fields_under(name):
            raise AttributeError(f"{name} is a struct or array, assign to its fields")
        else:
            # Never quietly grow a new attribute: a typo like
            # `sat.sleep_m = 5` should fail, not do nothing.
            raise AttributeError(self._layout.unknown(name))

    def __dir__(self):
        return sorted(set(super().__dir__()) | _children(self._layout, ""))

    def _resolve(self, path: str):
        """A field's value, or a Group if `path` names a struct or array."""
        if path in self._layout:
            return self.read(path)
        if self._fields_under(path):
            return Group(self, path)
        raise AttributeError(self._layout.unknown(path))

    def _fields_under(self, prefix: str) -> list[Field]:
        if not prefix:
            return list(self._layout.fields)
        return [
            f
            for f in self._layout.fields
            if f.name.startswith((prefix + ".", prefix + "["))
        ]

    # -- plumbing ------------------------------------------------------

    @staticmethod
    def _call(f: Field, op, *args) -> int:
        """Run a link op, naming the field in anything it raises."""
        try:
            return op(*args)
        except SatError as err:
            raise type(err)(f"{f.name}: {err}") from None

    def close(self) -> None:
        self._link.close()

    def __enter__(self) -> "Sat":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Sat {self._layout.name} on {self._link.transport!r}>"


class Group:
    """A nested struct or an array inside the slate, e.g. `sat.board_power`."""

    def __init__(self, sat: Sat, path: str):
        object.__setattr__(self, "_sat", sat)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._sat._resolve(f"{self._path}.{name}")

    def __setattr__(self, name: str, value) -> None:
        self._sat.write(self._name(f"{self._path}.{name}"), value)

    def __getitem__(self, index):
        return self._sat._resolve(self._index(index))

    def __setitem__(self, index, value) -> None:
        self._sat.write(self._name(self._index(index)), value)

    def dump(self) -> dict:
        """Every field in this group, read fresh, by full name."""
        return self._sat.dump(self._path)

    def __dir__(self):
        return sorted(_children(self._sat.layout, self._path + "."))

    def __repr__(self) -> str:
        return f"<Group {self._path}: {', '.join(sorted(dir(self)))}>"

    def _index(self, index) -> str:
        if isinstance(index, int):
            return f"{self._path}[{index}]"
        return f"{self._path}.{index}"  # group["voltage"] reads like an attribute

    def _name(self, path: str) -> str:
        if path not in self._sat.layout:
            raise AttributeError(self._sat.layout.unknown(path))
        return path


def _children(layout: Layout, prefix: str) -> set[str]:
    """The next attribute name down from `prefix`, for tab completion."""
    names = set()
    for f in layout.fields:
        if f.name.startswith(prefix):
            head = f.name[len(prefix) :].split(".")[0].split("[")[0]
            if head:
                names.add(head)
    return names


def connect(
    port: str | None = None,
    *,
    elf: str = DEFAULT_ELF,
    struct: str = DEFAULT_STRUCT,
    fake: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> Sat:
    """Open a board's slate.

    `port` is autodetected when there is exactly one pico attached. With
    `fake=True` there is no board at all: an in process one serves a zeroed
    slate of the right size, which is enough to try a script out.
    """
    lay = layout_mod.load(resolve_elf(elf), struct)
    if fake:
        transport = FakeBoard(lay.size).transport
    else:
        transport = SerialTransport(port or autodetect_port())
    return Sat(Link(transport, timeout=timeout), lay)


def resolve_elf(elf: str) -> str:
    """Locate the firmware elf, working around the bazel-bin symlink.

    Bazel repoints `bazel-bin` at whichever configuration it built last, so
    running the host tests leaves the default path aimed at a tree with no
    firmware in it. Rather than fail with a bare "no such file", ask bazel
    where the pico build actually puts things.
    """
    if os.path.exists(elf) or elf != DEFAULT_ELF:
        return elf

    try:
        out = subprocess.run(
            ["bazel", "cquery", "--config=pico", "--output=files", "//:blink"],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return elf  # no bazel, or no pico build yet; report the missing default

    for path in out.stdout.split():
        if path.endswith("/blink") and os.path.exists(path):
            return path
    return elf
