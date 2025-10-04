# Error Handling

Connect uses a standard set of error codes to indicate what went wrong with an RPC. Each error includes a `Code`, a human-readable message, and optionally some typed error details. This document explains how to work with errors in connect-python.

## Error codes

Connect defines 16 error codes. Each code maps to a specific HTTP status code when using the Connect protocol over HTTP. The full list of codes is available in the `connectrpc.code.Code` enum:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `CANCELED` | 499 | RPC canceled, usually by the caller |
| `UNKNOWN` | 500 | Catch-all for errors of unclear origin |
| `INVALID_ARGUMENT` | 400 | Request is invalid, regardless of system state |
| `DEADLINE_EXCEEDED` | 504 | Deadline expired before RPC could complete |
| `NOT_FOUND` | 404 | Requested resource can't be found |
| `ALREADY_EXISTS` | 409 | Caller attempted to create a resource that already exists |
| `PERMISSION_DENIED` | 403 | Caller isn't authorized to perform the operation |
| `RESOURCE_EXHAUSTED` | 429 | Operation can't be completed because some resource is exhausted |
| `FAILED_PRECONDITION` | 400 | Operation can't be completed because system isn't in required state |
| `ABORTED` | 409 | Operation was aborted, often due to concurrency issues |
| `OUT_OF_RANGE` | 400 | Operation was attempted past the valid range |
| `UNIMPLEMENTED` | 501 | Operation isn't implemented, supported, or enabled |
| `INTERNAL` | 500 | An invariant expected by the system has been broken |
| `UNAVAILABLE` | 503 | Service is currently unavailable, usually transiently |
| `DATA_LOSS` | 500 | Unrecoverable data loss or corruption |
| `UNAUTHENTICATED` | 401 | Caller doesn't have valid authentication credentials |

## Raising errors in servers

To return an error from a server handler, raise a `ConnectError`:

=== "ASGI"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from connectrpc.request import RequestContext
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class GreetService:
        async def greet(self, request: GreetRequest, ctx: RequestContext) -> GreetResponse:
            if not request.name:
                raise ConnectError(Code.INVALID_ARGUMENT, "name is required")
            return GreetResponse(greeting=f"Hello, {request.name}!")
    ```

=== "WSGI"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from connectrpc.request import RequestContext
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class GreetServiceSync:
        def greet(self, request: GreetRequest, ctx: RequestContext) -> GreetResponse:
            if not request.name:
                raise ConnectError(Code.INVALID_ARGUMENT, "name is required")
            return GreetResponse(greeting=f"Hello, {request.name}!")
    ```

Any `ConnectError` raised in a handler will be serialized and sent to the client. If you raise any other exception type, it will be converted to a `ConnectError` with code `INTERNAL` and a generic error message. The original exception details will be logged but not sent to the client to avoid leaking sensitive information.

## Handling errors in clients

When a client receives an error response, the client stub raises a `ConnectError`:

=== "Async"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest

    async def main():
        client = GreetServiceClient("http://localhost:8000")
        try:
            response = await client.greet(GreetRequest(name=""))
        except ConnectError as e:
            if e.code == Code.INVALID_ARGUMENT:
                print(f"Invalid request: {e.message}")
            else:
                print(f"RPC failed: {e.code} - {e.message}")
    ```

=== "Sync"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest

    def main():
        client = GreetServiceClientSync("http://localhost:8000")
        try:
            response = client.greet(GreetRequest(name=""))
        except ConnectError as e:
            if e.code == Code.INVALID_ARGUMENT:
                print(f"Invalid request: {e.message}")
            else:
                print(f"RPC failed: {e.code} - {e.message}")
    ```

Client-side errors (like network failures, timeouts, or protocol violations) are also raised as `ConnectError` instances with appropriate error codes.

## Error details

In addition to a code and message, errors can include typed details. This is useful for providing structured information about validation errors, rate limiting, retry policies, and more.

### Adding details to errors

To add details to an error, pass protobuf messages to the `details` parameter:

```python
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext
from google.protobuf.struct_pb2 import Struct, Value

async def create_user(self, request: CreateUserRequest, ctx: RequestContext) -> CreateUserResponse:
    if not request.email:
        # Create structured error details using Struct
        error_detail = Struct(fields={
            "field": Value(string_value="email"),
            "issue": Value(string_value="Email is required")
        })

        raise ConnectError(
            Code.INVALID_ARGUMENT,
            "Invalid user request",
            details=[error_detail]
        )
    # ... rest of implementation
```

You can include multiple detail messages of different types:

```python
from google.protobuf.struct_pb2 import Struct, Value

validation_errors = Struct(fields={
    "email": Value(string_value="Must be a valid email address"),
    "age": Value(string_value="Must be at least 18")
})

help_info = Struct(fields={
    "documentation": Value(string_value="https://docs.example.com/validation")
})

raise ConnectError(
    Code.INVALID_ARGUMENT,
    "Validation failed",
    details=[validation_errors, help_info]
)
```

If you have the `googleapis-common-protos` package installed, you can use the standard error detail types like `BadRequest`:

```python
from google.rpc.error_details_pb2 import BadRequest

bad_request = BadRequest()
violation = bad_request.field_violations.add()
violation.field = "email"
violation.description = "Must be a valid email address"

raise ConnectError(
    Code.INVALID_ARGUMENT,
    "Invalid email format",
    details=[bad_request]
)
```

### Reading error details

On the client side, error details are available through the `details` property. Details are stored as `google.protobuf.Any` messages and can be unpacked to their original types:

```python
from google.protobuf.struct_pb2 import Struct

try:
    response = await client.some_method(request)
except ConnectError as e:
    for detail in e.details:
        # Unpack the detail to the expected type
        unpacked = Struct()
        if detail.Unpack(unpacked):
            # Successfully unpacked
            print(f"Error detail: {unpacked}")
```

You can also check the type before unpacking using the `.Is()` method:

```python
from google.protobuf.struct_pb2 import Struct

try:
    response = await client.some_method(request)
except ConnectError as e:
    for detail in e.details:
        if detail.Is(Struct.DESCRIPTOR):
            unpacked = Struct()
            detail.Unpack(unpacked)
            print(f"Struct detail: {unpacked}")
```

### Common error detail types

You can use any protobuf message type for error details. Some commonly used types include:

**Built-in types** (available in `google.protobuf`):
- `Struct`: Generic structured data
- `Any`: Wrap arbitrary protobuf messages
- `Duration`: Time durations
- `Timestamp`: Specific points in time

**Standard error details** (requires `googleapis-common-protos` package):

Google provides standard error detail types in the `google.rpc.error_details_pb2` module:

- `BadRequest`: Describes violations in a client request
- `Help`: Provides links to documentation or related resources
- `RetryInfo`: Tells the client when to retry
- `QuotaFailure`: Describes quota violations
- `PreconditionFailure`: Describes failed preconditions
- `ErrorInfo`: Provides structured error metadata with a reason, domain, and metadata

To use these types, install the package:

```bash
pip install googleapis-common-protos
```

Example with `RetryInfo`:

```python
from google.protobuf.duration_pb2 import Duration
from google.rpc.error_details_pb2 import RetryInfo

retry_info = RetryInfo()
retry_info.retry_delay.CopyFrom(Duration(seconds=30))

raise ConnectError(
    Code.RESOURCE_EXHAUSTED,
    "Rate limit exceeded",
    details=[retry_info]
)
```

## Error handling in interceptors

Interceptors can catch and transform errors. This is useful for adding context, converting error types, or implementing retry logic:

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
                print(f"Error in {ctx.method()}: {e.code} - {e.message}")
                # Re-raise the error
                raise
            except Exception as e:
                # Convert unexpected errors to ConnectError
                print(f"Unexpected error in {ctx.method()}: {e}")
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
                print(f"Error in {ctx.method()}: {e.code} - {e.message}")
                # Re-raise the error
                raise
            except Exception as e:
                # Convert unexpected errors to ConnectError
                print(f"Unexpected error in {ctx.method()}: {e}")
                raise ConnectError(Code.INTERNAL, "An unexpected error occurred")
    ```

## Best practices

### Choose appropriate error codes

Select error codes that accurately reflect the situation:

- Use `INVALID_ARGUMENT` for malformed requests that should never be retried
- Use `FAILED_PRECONDITION` for requests that might succeed if the system state changes
- Use `UNAVAILABLE` for transient failures that should be retried
- Use `INTERNAL` sparingly - it indicates a bug in your code

### Provide helpful messages

Error messages should help the caller understand what went wrong and how to fix it:

```python
# Good
raise ConnectError(Code.INVALID_ARGUMENT, "email must contain an @ symbol")

# Less helpful
raise ConnectError(Code.INVALID_ARGUMENT, "invalid input")
```

### Use error details for structured data

Rather than encoding structured information in error messages, use typed error details:

```python
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

### Don't leak sensitive information

Avoid including sensitive data in error messages or details that will be sent to clients:

```python
# Bad - leaks internal details
raise ConnectError(Code.INTERNAL, f"Database query failed: {sql_query}")

# Good - generic message
raise ConnectError(Code.INTERNAL, "Failed to complete request")
```

### Handle timeouts appropriately

Client timeouts are represented with `Code.DEADLINE_EXCEEDED`:

```python
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from greet.v1.greet_connect import GreetServiceClient
from greet.v1.greet_pb2 import GreetRequest

async with GreetServiceClient("http://localhost:8000") as client:
    try:
        response = await client.greet(GreetRequest(name="World"), timeout_ms=1000)
    except ConnectError as e:
        if e.code == Code.DEADLINE_EXCEEDED:
            print("Operation timed out")
```

### Consider retry logic

Some errors are retriable. Use appropriate error codes to signal this:

```python
import asyncio
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from greet.v1.greet_connect import GreetServiceClient
from greet.v1.greet_pb2 import GreetRequest

async def call_with_retry(client: GreetServiceClient, request: GreetRequest, max_attempts: int = 3):
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
