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
        return eliza_pb2.SayResponse(sentence=f"You said: {req.sentence}")

    async def converse(self, req: AsyncIterator[eliza_pb2.ConverseRequest]) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        async for msg in req:
            yield eliza_pb2.ConverseResponse(sentence=f"You said: {msg.sentence}")
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
        return eliza_pb2.SayResponse(sentence=f"You said: {req.msg.sentence}")

    def converse(self, req: Iterator[eliza_pb2.ConverseRequest]) -> Iterator[eliza_pb2.ConverseResponse]:
        for msg in req:
            yield eliza_pb2.ConverseResponse(sentence=f"You said: {msg.sentence}")
```

## Error Handling Best Practices

### Choosing appropriate error codes

Select error codes that accurately reflect the situation:

- Use `INVALID_ARGUMENT` for malformed requests that should never be retried
- Use `FAILED_PRECONDITION` for requests that might succeed if the system state changes
- Use `UNAVAILABLE` for transient failures that should be retried
- Use `INTERNAL` sparingly - it indicates a bug in your code

For more detailed guidance on choosing error codes, see the [Connect protocol documentation](https://connectrpc.com/docs/protocol#error-codes).

### Providing helpful error messages

Error messages should help the caller understand what went wrong and how to fix it:

```python
# Good - specific and actionable
raise ConnectError(Code.INVALID_ARGUMENT, "email must contain an @ symbol")

# Less helpful - too vague
raise ConnectError(Code.INVALID_ARGUMENT, "invalid input")
```

### Using error details for structured data

Rather than encoding structured information in error messages, use typed error details. For example:

```python
from google.rpc.error_details_pb2 import BadRequest

# Good - structured details
bad_request = BadRequest()
for field, error in validation_errors.items():
    violation = bad_request.field_violations.add()
    violation.field = field
    violation.description = error
raise ConnectError(Code.INVALID_ARGUMENT, "Validation failed", details=[bad_request])

# Less structured - information in message
raise ConnectError(
    Code.INVALID_ARGUMENT,
    f"Validation failed: email: {email_error}, name: {name_error}"
)
```

**Note**: While error details provide structured error information, they require client-side deserialization to be fully useful for debugging. Make sure to document expected error detail types in your API documentation to help consumers properly handle them.

### Security considerations

Avoid including sensitive data in error messages or details that will be sent to clients. For example:

```python
# Bad - leaks internal details
raise ConnectError(Code.INTERNAL, f"Database query failed: {sql_query}")

# Good - generic message
raise ConnectError(Code.INTERNAL, "Failed to complete request")
```

### Handling timeouts

Client timeouts are represented with `Code.DEADLINE_EXCEEDED`:

```python
from connectrpc.code import Code
from connectrpc.errors import ConnectError

async with GreetServiceClient("http://localhost:8000") as client:
    try:
        response = await client.greet(GreetRequest(name="World"), timeout_ms=1000)
    except ConnectError as e:
        if e.code == Code.DEADLINE_EXCEEDED:
            print("Operation timed out")
```

### Implementing retry logic

Some errors are retriable. Use appropriate error codes to signal this. Here's an example implementation:

```python
import asyncio
from connectrpc.code import Code
from connectrpc.errors import ConnectError

async def call_with_retry(client, request, max_attempts=3):
    """Retry logic for transient failures."""
    for attempt in range(max_attempts):
        try:
            return await client.greet(request)
        except ConnectError as e:
            # Only retry transient errors
            if e.code == Code.UNAVAILABLE and attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

### Error transformation in interceptors

Interceptors can catch and transform errors. This is useful for adding context, converting error types, or implementing retry logic. For example:

=== "ASGI"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError

    class ErrorLoggingInterceptor:
        async def intercept_unary(self, call_next, request, ctx):
            try:
                return await call_next(request, ctx)
            except ConnectError as e:
                # Log the error with context
                method = ctx.method()
                print(f"Error in {method.service_name}/{method.name}: {e.code} - {e.message}")
                # Re-raise the error
                raise
            except Exception as e:
                # Convert unexpected errors to ConnectError
                method = ctx.method()
                print(f"Unexpected error in {method.service_name}/{method.name}: {e}")
                raise ConnectError(Code.INTERNAL, "An unexpected error occurred")
    ```

=== "WSGI"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError

    class ErrorLoggingInterceptor:
        def intercept_unary_sync(self, call_next, request, ctx):
            try:
                return call_next(request, ctx)
            except ConnectError as e:
                # Log the error with context
                method = ctx.method()
                print(f"Error in {method.service_name}/{method.name}: {e.code} - {e.message}")
                # Re-raise the error
                raise
            except Exception as e:
                # Convert unexpected errors to ConnectError
                method = ctx.method()
                print(f"Unexpected error in {method.service_name}/{method.name}: {e}")
                raise ConnectError(Code.INTERNAL, "An unexpected error occurred")
    ```
