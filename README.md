# connect-python

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/connectrpc/connect-python/actions/workflows/ci.yaml/badge.svg)](https://github.com/connectrpc/connect-python/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/connectrpc/connect-python/graph/badge.svg)](https://codecov.io/github/connectrpc/connect-python)
[![PyPI version](https://img.shields.io/pypi/v/connect-python)](https://pypi.org/project/connect-python)

A Python implementation of [Connect](https://connectrpc.com/): Protobuf RPC that works.

This repo provides a Python implementation of Connect, including both client and server support. It includes a protoc plugin that generates typed client stubs and server interfaces from your `.proto` files, along with runtime libraries for both synchronous and asynchronous code.

## Features

- **Clients**: Both synchronous and asynchronous clients backed by [httpx](https://www.python-httpx.org/)
- **Servers**: WSGI and ASGI server implementations for use with any Python app server
- **Type Safety**: Fully type-annotated, including the generated code
- **Compression**: Built-in support for gzip, brotli, and zstd compression
- **Interceptors**: Server-side and client-side interceptors for cross-cutting concerns
- **Streaming**: Full support for server, client, and bidirectional streaming
- **Standards Compliant**: Verified implementation using the official
  [Connect conformance](https://github.com/connectrpc/conformance) test
  suite

## Installation

### Install the runtime library

```bash
pip install connect-python
```

Or with your preferred package manager:

```bash
# Using uv
uv add connect-python

# Using poetry
poetry add connect-python
```

### Install the code generator

With a protobuf definition in hand, you can generate stub code. This is
easiest using buf, but you can also use protoc if you're feeling
masochistic.

A reasonable `buf.gen.yaml`:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: .
  - remote: buf.build/protocolbuffers/pyi
    out: .
  - remote: buf.build/connectrpc/python
    out: .
```

Or, you can install the compiler (e.g. `pip install protoc-gen-connect-python`), and
it can be referenced as `protoc-gen-connect-python`.
Then, you can use `protoc-gen-connect-python` as a local plugin:

```yaml
  - local: .venv/bin/protoc-gen-connect-python
    out: .
```

Alternatively, download a precompiled binary from the
[releases](https://github.com/connectrpc/connect-python/releases).

`protoc-gen-connect-python` is only needed for code generation. Your actual
application should include `connect-python` as a dependency for the runtime
component.

For more usage details, see the [docs](./docs/usage.md).

### Basic Client Usage

```python
import httpx
from your_service_pb2 import HelloRequest, HelloResponse
from your_service_connect import HelloServiceClient

# Create async client
async def main():
    async with httpx.AsyncClient() as session:
        client = HelloServiceClient(
            base_url="https://api.example.com",
            session=session
        )

        # Make a unary RPC call
        response = await client.say_hello(HelloRequest(name="World"))
        print(response.message)  # "Hello, World!"
```

### Basic Server Usage

```python
from connectrpc.request import RequestContext
from your_service_pb2 import HelloRequest, HelloResponse
from your_service_connect import HelloService, HelloServiceASGIApplication

class MyHelloService(HelloService):
    async def say_hello(self, request: HelloRequest, ctx: RequestContext) -> HelloResponse:
        return HelloResponse(message=f"Hello, {request.name}!")

# Create ASGI app
app = HelloServiceASGIApplication(MyHelloService())

# Run with any ASGI server like uvicorn and hypercorn:
# uvicorn server:app --port 8080
```

### Basic Client Usage (Synchronous)

```python
import httpx
from your_service_pb2 import HelloRequest
from your_service_connect import HelloServiceClientSync

# Create sync client
def main():
    with httpx.Client() as session:
        client = HelloServiceClientSync(
            base_url="https://api.example.com",
            session=session
        )

        # Make a unary RPC call
        response = client.say_hello(HelloRequest(name="World"))
        print(response.message)  # "Hello, World!"

if __name__ == "__main__":
    main()
```

For more detailed usage including streaming, interceptors, and advanced features, see the [documentation](./docs/usage.md).

## Streaming Support

connect-python supports all RPC streaming types:

- **Unary**: Single request, single response
- **Server Streaming**: Single request, multiple responses
- **Client Streaming**: Multiple requests, single response
- **Bidirectional Streaming**: Multiple requests, multiple responses

### Server Streaming

Single request, multiple responses:

```python
# Server implementation
async def make_hats(self, req: Size, ctx: RequestContext) -> AsyncIterator[Hat]:
    for i in range(3):
        yield Hat(size=req.inches + i, color=["red", "green", "blue"][i])

# Client usage
async for hat in client.make_hats(Size(inches=12)):
    print(f"Received: {hat}")
```

### Client Streaming

Multiple requests, single response:

```python
# Server implementation
async def collect_sizes(self, reqs: AsyncIterator[Size], ctx: RequestContext) -> Summary:
    total = 0
    count = 0
    async for size in reqs:
        total += size.inches
        count += 1
    return Summary(total=total, average=total/count if count else 0)

# Client usage
async def send_sizes():
    for i in range(5):
        yield Size(inches=i * 2)

summary = await client.collect_sizes(send_sizes())
```

### Bidirectional Streaming

Multiple requests and responses:

```python
# Server implementation (like the Eliza chatbot)
async def converse(self, reqs: AsyncIterator[ConverseRequest], ctx: RequestContext) -> AsyncIterator[ConverseResponse]:
    async for req in reqs:
        # Process and respond to each message
        reply = process_message(req.sentence)
        yield ConverseResponse(sentence=reply)

# Client usage
async def chat():
    yield ConverseRequest(sentence="Hello")
    yield ConverseRequest(sentence="How are you?")

async for response in client.converse(chat()):
    print(f"Response: {response.sentence}")
```

### Streaming Notes

- **HTTP/2 ASGI servers** (Hypercorn, Daphne): Support all streaming types including full-duplex bidirectional
- **HTTP/1.1 servers**: Support half-duplex bidirectional streaming only
- **WSGI servers**: Support streaming but not full-duplex bidirectional due to protocol limitations

- **Clients**: Support half-duplex bidirectional streaming only

## Examples

The `example/` directory contains complete working examples demonstrating all features:

- **Eliza Chatbot**: A Connect implementation of the classic ELIZA psychotherapist chatbot
  - `eliza_service.py` - Async ASGI server implementation
  - `eliza_service_sync.py` - Synchronous WSGI server implementation
  - `eliza_client.py` - Async client example
  - `eliza_client_sync.py` - Synchronous client example
- **All streaming patterns**: Unary, server streaming, client streaming, and bidirectional
- **Integration examples**: Starlette, Flask, and other frameworks

Run the Eliza example:

```bash
# Start the server
cd example
uvicorn example.eliza_service:app --port 8080

# In another terminal, run the client
python -m example.eliza_client
```

## Supported Protocols

- ✅ Connect Protocol over HTTP/1.1 and HTTP/2
- 🚧 gRPC Protocol support is not available
- 🚧 gRPC-Web Protocol support is not available

## Server Runtime Options

For ASGI servers:

- [Uvicorn](https://www.uvicorn.org/) - Lightning-fast ASGI server
- [Daphne](https://github.com/django/daphne) - Django Channels' ASGI server with HTTP/2 support
- [Hypercorn](https://gitlab.com/pgjones/hypercorn) - ASGI server with HTTP/2 and HTTP/3 support

For WSGI servers:

- [Gunicorn](https://gunicorn.org/) - Python WSGI HTTP Server
- [uWSGI](https://uwsgi-docs.readthedocs.io/) - Full-featured application server
- Any WSGI-compliant server

For testing, you'll need the [buf CLI](https://buf.build/docs/installation) for running conformance tests.

## WSGI Support

connect-python provides full WSGI support via `ConnectWSGIApplication` for synchronous Python applications. This enables integration with traditional WSGI servers like Gunicorn and uWSGI.

```python
from connectrpc.request import RequestContext
from connectrpc.server import ConnectWSGIApplication
from your_service_pb2 import Request, Response
from your_service_connect import YourService, YourServiceWSGIApplication

class YourServiceImpl(YourService):
    def your_method(self, request: Request, ctx: RequestContext) -> Response:
        # Synchronous implementation
        return Response(message="Hello from WSGI")

    # WSGI also supports streaming (except full-duplex bidirectional)
    def stream_data(self, request: Request, ctx: RequestContext) -> Iterator[Response]:
        for i in range(3):
            yield Response(message=f"Message {i}")

# Create WSGI application
app = YourServiceWSGIApplication(YourServiceImpl())

# Run with gunicorn: gunicorn server:app
```

## Compression Support

connect-python supports multiple compression algorithms:

- **gzip**: Built-in support, always available
- **brotli**: Available when `brotli` package is installed
- **zstd**: Available when `zstandard` package is installed

Compression is automatically negotiated between client and server based on the `Accept-Encoding` and `Content-Encoding` headers.

## Interceptors

### Server-Side Interceptors

Interceptors allow you to add cross-cutting concerns like authentication, logging, and metrics:

```python
from connectrpc.interceptor import Interceptor

class LoggingInterceptor(Interceptor):
    async def intercept(self, method, request, context, next_handler):
        print(f"Handling {method} request")
        response = await next_handler(request, context)
        print(f"Completed {method} request")
        return response

# Add to your application
app = HelloServiceASGIApplication(
    MyHelloService(),
    interceptors=[LoggingInterceptor()]
)
```

### Client-Side Interceptors

Clients also support interceptors for request/response processing:

```python
client = HelloServiceClient(
    base_url="https://api.example.com",
    session=session,
    interceptors=[AuthInterceptor(), RetryInterceptor()]
)
```

## Advanced Features

### Connect GET Support

connect-python automatically enables GET request support for methods marked with `idempotency_level = NO_SIDE_EFFECTS` in your proto files:

```proto
service YourService {
  // This method will support both GET and POST requests
  rpc GetData(Request) returns (Response) {
    option idempotency_level = NO_SIDE_EFFECTS;
  }
}
```

Clients can use GET requests automatically:

```python
# The client will use GET for idempotent methods
response = await client.get_data(request)
```

### CORS Support

connect-python works with any ASGI CORS middleware. For example, using Starlette:

```python
from starlette.middleware.cors import CORSMiddleware
from starlette.applications import Starlette

app = Starlette()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# Mount your Connect application
```

### Message Size Limits

Protect against resource exhaustion by limiting message sizes:

```python
# ASGI application with 1MB limit
app = YourServiceASGIApplication(
    service,
    read_max_bytes=1024 * 1024  # 1MB
)

# Client with message size limit
client = YourServiceClient(
    base_url="https://api.example.com",
    session=session,
    read_max_bytes=1024 * 1024
)
```

When exceeded, returns `RESOURCE_EXHAUSTED` error.

### Proto Editions Support

connect-python supports Proto Editions 2023:

```proto
edition = "2023";

package your.service;

service YourService {
  rpc YourMethod(Request) returns (Response);
}
```

## Development

We use `ruff` for linting and formatting, and `pyright` for type checking.

We rely on the conformance test suit (in
[./conformance](./conformance)) to verify behavior.

Set up a virtual env:

```sh
uv sync
```

Then, use `uv run just` to do development checks, or check out `uv run just --list` for other targets.
`just` is run via `uv` as a development dependency, but you can also install it globally and omit the `uv run` from the commands.

## Status

This project is in alpha and is being actively developed. Expect breaking changes.

## Legal

Offered under the [Apache 2 license](/LICENSE).
