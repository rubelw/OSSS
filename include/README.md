# greenlet — Lightweight Coroutine Extension (Installed Headers)

The `include/site/python3.11/greenlet/` directory contains the installed **header and support files** for the `greenlet` Python extension module compiled into your local Python environment. These files are generated when `greenlet` is installed and are required for C-level integration and builds that depend on greenlet internals.

## What is `greenlet`?

`greenlet` provides **lightweight coroutines** that allow manual context switching between execution stacks within a single OS thread.  
It is a foundational component used by libraries such as `gevent` to support cooperative multitasking.

Characteristics:
- user-controlled scheduling
- minimal overhead coroutine switching
- runs within a single OS thread
- provides `greenlet.greenlet(...)` for creating execution contexts

## Why does this directory exist?

This directory contains **C header files and build artifacts** that enable:
- compilation of greenlet itself
- dependency modules to bind directly into greenlet internals
- integration with projects that extend or optimize coroutines

The location:
```
include/site/python3.11/greenlet/
```
matches Python's `sysconfig.get_paths()["include"]` resolution and is part of the interpreter's development headers.

## Typical files

You may see files similar to:

```
greenlet/
├── greenlet.h          # C API definitions
├── greenlet_internal.h # internal coroutine state structures
├── slp_platformselect.h
└── ...
```

(Exact layout depends on greenlet version and platform.)

These are **not Python source files** — they are C headers used when building or extending greenlet.

## Example: C-level usage

```c
#include <Python.h>
#include <greenlet/greenlet.h>

static PyObject* example_switch(PyObject* self, PyObject* args) {
    // this would interact with the active greenlet state
    // real usage requires careful stack handling
    int active = PyGreenlet_ACTIVE();
    return PyBool_FromLong(active);
}
```

> Note: this is *illustrative only* — directly interfacing with greenlet internals is uncommon unless you are writing coroutine frameworks.

## When does OSSS use greenlet?

OSSS does **not directly import greenlet** in most modules.  
Instead, it appears because:
- dependencies use asynchronous networking or coroutine frameworks
- indirect dependencies such as `gevent` or tooling require greenlet

If greenlet disappears on reinstall, it generally means no installed dependencies require it.

## Installing / ensuring availability

```bash
pip install greenlet
```

To inspect compile paths:

```bash
python - <<'EOF'
import greenlet, sysconfig
print("greenlet include:", sysconfig.get_paths()["include"])
print("greenlet version:", greenlet.__version__)
EOF
```

## License

This directory contains build artifacts of `greenlet`, covered by the greenlet project license:
https://github.com/python-greenlet/greenlet

