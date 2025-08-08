# Getting Started

## Installation

### Basic Client

For basic client functionality:
```bash
pip install connect-python
```

### Code Generation

For code generation (protoc plugin):
```bash
pip install connect-python[compiler]
```

## Code Generation

With a protobuf definition in hand, you can generate a client. This is
easiest using buf, but you can also use protoc directly.

Install the compiler (eg `pip install connect-python[compiler]`), and
it can be referenced as `protoc-gen-connect-python`.

### Using Buf (Recommended)

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

### Using protoc

```bash
protoc --plugin=protoc-gen-connect-python=.venv/bin/protoc-gen-connect-python \
       --connect_python_out=. \
       --python_out=. \
       --pyi_out=. \
       your_service.proto
```

## Example Service Definition

If you have a proto definition like this:

```proto
service ElizaService {
  rpc Say(SayRequest) returns (SayResponse) {}
  rpc Converse(stream ConverseRequest) returns (stream ConverseResponse) {}
  rpc Introduce(IntroduceRequest) returns (stream IntroduceResponse) {}
  rpc Pontificate(stream PontificateRequest) returns (PontificateResponse) {}
}
```

## Generated Client

Then the generated client will have methods like this (optional arguments have been elided for clarity):

```python
class ElizaServiceClient:
    def __init__(self, base_url: str, http_client: urllib3.PoolManager):
        ...

    # Unary (no streams)
    def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        ...

    # Bidirectional (both sides stream)
    def converse(self, req: Iterator[eliza_pb2.ConverseRequest]) -> Iterator[eliza_pb2.SayResponse]:
        ...

    # Server streaming (client sends one message, server sends a stream)
    def introduce(self, req: eliza_pb2.IntroduceRequest) -> Iterator[eliza_pb2.IntroduceResponse]:
        ...

    # Client streaming (client sends a stream, server sends one message back)
    def pontificate(self, req: Iterator[eliza_pb2.PontificateRequest]) -> eliza_pb2.PontificateResponse:
        ...
```

## Next Steps

- Learn about [Usage](usage.md) patterns
- Explore the [API Reference](api/index.md)
- Check out [Examples](examples/index.md)