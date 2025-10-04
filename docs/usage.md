# Usage Guide

## Basic Client Usage

### Asynchronous Client

```python
from your_generated_code.eliza_connect import ElizaServiceClient
from your_generated_code import eliza_pb2

async def main():
    async with ElizaServiceClient("https://demo.connectrpc.com") as eliza_client:
        # Unary responses: await and get the response message back
        response = await eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
        print(f"  Eliza says: {response.sentence}")

        # Streaming responses: use async for to iterate over messages in the stream
        req = eliza_pb2.IntroduceRequest(name="Henry")
        async for response in eliza_client.introduce(req):
            print(f"   Eliza: {response.sentence}")

        # Streaming requests: send an iterator, get a single message
        async def pontificate_requests():
            yield eliza_pb2.PontificateRequest(sentence="I have many things on my mind.")
            yield eliza_pb2.PontificateRequest(sentence="But I will save them for later.")
        response = await eliza_client.pontificate(pontificate_requests())
        print(f"    Eliza responds: {response.sentence}")

        # Bidirectional RPCs: send an iterator, get an iterator
        async def converse_requests():
            yield eliza_pb2.ConverseRequest(sentence="I have been having trouble communicating.")
            yield eliza_pb2.ConverseRequest(sentence="But structured RPCs are pretty great!")
            yield eliza_pb2.ConverseRequest(sentence="What do you think?")
        async for response in eliza_client.converse(converse_requests()):
            print(f"    Eliza: {response.sentence}")
```

### Synchronous Client

```python
from your_generated_code.eliza_connect import ElizaServiceClientSync
from your_generated_code import eliza_pb2

# Create client
eliza_client = ElizaServiceClientSync("https://demo.connectrpc.com")

# Unary responses:
response = eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
print(f"  Eliza says: {response.sentence}")

# Streaming responses: use 'for' to iterate over messages in the stream
req = eliza_pb2.IntroduceRequest(name="Henry")
for response in eliza_client.introduce(req):
    print(f"   Eliza: {response.sentence}")

# Streaming requests: send an iterator, get a single message
requests = [
    eliza_pb2.PontificateRequest(sentence="I have many things on my mind."),
    eliza_pb2.PontificateRequest(sentence="But I will save them for later."),
]
response = eliza_client.pontificate(requests)
print(f"    Eliza responds: {response.sentence}")

# Bidirectional RPCs: send an iterator, get an iterator.
requests = [
    eliza_pb2.ConverseRequest(sentence="I have been having trouble communicating."),
    eliza_pb2.ConverseRequest(sentence="But structured RPCs are pretty great!"),
    eliza_pb2.ConverseRequest(sentence="What do you think?")
]
for response in eliza_client.converse(requests):
    print(f"    Eliza: {response.sentence}")
```

## Advanced Usage

### Sending Extra Headers

All RPC methods take an `headers` argument; you can use a `dict[str, str]` or
a `Headers` object if needing to send multiple values for a key.

```python
eliza_client.say(req, headers={"X-Favorite-RPC": "Connect"})
```

### Per-request Timeouts

All RPC methods take a `timeout_ms: int` argument:

```python
eliza_client.say(req, timeout_ms=250)
```

The timeout will be used in two ways:

1. It will be set in the `Connect-Timeout-Ms` header, so the server will be informed of the deadline
2. The HTTP client will be informed, and will close the request if the timeout expires
3. For asynchronous clients, the RPC invocation itself will be timed-out without relying on the I/O stack

### Response Metadata

For access to response headers or trailers, wrap invocations with the `ResponseMetadata` context manager.

```python
with ResponseMetadata() as meta:
    response = eliza_client.say(req)
    print(response.sentence)
    print(meta.headers())
    print(meta.trailers())
```

## Server Implementation

### ASGI Server

The generated code includes a class to mount an object implementing your service as a ASGI application:

```python
class ElizaServiceASGIApplication(service: ElizaService):
    ...
```

Your implementation needs to follow the `ElizaService` protocol:

```python
from typing import AsyncIterator
from connectrpc.request import RequestContext
from your_generated_code import eliza_pb2

class ElizaServiceImpl:
    async def say(self, request: eliza_pb2.SayRequest, ctx: RequestContext) -> eliza_pb2.SayResponse:
        return eliza_pb2.SayResponse(sentence=f"You said: {request.sentence}")

    async def converse(self, request: AsyncIterator[eliza_pb2.ConverseRequest], ctx: RequestContext) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        async for message in request:
            yield eliza_pb2.ConverseResponse(sentence=f"You said: {message.sentence}")
```

### WSGI Server

The generated code includes a class to mount an object implementing your service as a WSGI application:

```python
class ElizaServiceWSGIApplication(service: ElizaServiceSync):
    ...
```

Your implementation needs to follow the `ElizaServiceSync` protocol:

```python
from typing import Iterator
from connectrpc.request import RequestContext
from your_generated_code import eliza_pb2

class ElizaServiceImpl:
    def say(self, request: eliza_pb2.SayRequest, ctx: RequestContext) -> eliza_pb2.SayResponse:
        return eliza_pb2.SayResponse(sentence=f"You said: {request.sentence}")

    def converse(self, request: Iterator[eliza_pb2.ConverseRequest], ctx: RequestContext) -> Iterator[eliza_pb2.ConverseResponse]:
        for message in request:
            yield eliza_pb2.ConverseResponse(sentence=f"You said: {message.sentence}")
```
