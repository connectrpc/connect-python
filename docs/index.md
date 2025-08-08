# Connect Python

A Python implementation of the Connect RPC framework.

This provides an asynchronous client runtime, as well as a client code
generator, to let Python programs communicate with Connect servers.

```{toctree}
:maxdepth: 2
:caption: Contents:

getting-started
usage
api/index
examples/index
development
```

## Features

- Straightforward, simple client backed by urllib3
- *and also* async, `aiohttp`-powered client for efficient use in
  real production servers.
- Fully type-annotated, including the generated code, and verified
  with mypy.
- Verified implementation using the official
  [conformance](https://github.com/connectprc/conformance) test
  suite.

## Installation

For basic client functionality:
```bash
pip install connect-python
```

For code generation (protoc plugin):
```bash
pip install connect-python[compiler]
```

## Quick Start

With a protobuf definition in hand, you can generate a client. This is
easiest using buf, but you can also use protoc if you're feeling
masochistic.

Install the compiler (eg `pip install connect-python[compiler]`), and
it can be referenced as `protoc-gen-connect-python`.

A reasonable `buf.gen.yaml`:
```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: .
  - remote: buf.build/protocolbuffers/pyi
    out: .
  - local: .venv/bin/protoc-gen-connect-python
    out: .
```

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`