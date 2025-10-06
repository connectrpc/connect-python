# Errors

Similar to the familiar "404 Not Found" and "500 Internal Server Error" status codes in HTTP, Connect uses a set of [16 error codes](https://connectrpc.com/docs/protocol#error-codes). These error codes are designed to work consistently across Connect, gRPC, and gRPC-Web protocols.

## Working with errors

Connect handlers raise errors using `ConnectError`:

=== "ASGI"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from connectrpc.request import RequestContext

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

    def greet(self, request: GreetRequest, ctx: RequestContext) -> GreetResponse:
        if not request.name:
            raise ConnectError(Code.INVALID_ARGUMENT, "name is required")
        return GreetResponse(greeting=f"Hello, {request.name}!")
    ```

Clients catch errors the same way:

=== "Async"

    ```python
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError

    async with GreetServiceClient("http://localhost:8000") as client:
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

    with GreetServiceClientSync("http://localhost:8000") as client:
        try:
            response = client.greet(GreetRequest(name=""))
        except ConnectError as e:
            if e.code == Code.INVALID_ARGUMENT:
                print(f"Invalid request: {e.message}")
            else:
                print(f"RPC failed: {e.code} - {e.message}")
    ```

## Error codes

Connect uses a set of [16 error codes](https://connectrpc.com/docs/protocol#error-codes). The `code` property of a `ConnectError` holds one of these codes. All error codes are available through the `Code` enumeration:

```python
from connectrpc.code import Code

code = Code.INVALID_ARGUMENT
code.value  # "invalid_argument"

# Access by name
Code["INVALID_ARGUMENT"]  # Code.INVALID_ARGUMENT
```

## Error messages

The `message` property contains a descriptive error message. In most cases, the message is provided by the backend implementing the service:

```python
try:
    response = await client.greet(GreetRequest(name=""))
except ConnectError as e:
    print(e.message)  # "name is required"
```

## Error details

Errors can include strongly-typed details using protobuf messages:

```python
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext
from google.protobuf.struct_pb2 import Struct, Value

async def create_user(self, request: CreateUserRequest, ctx: RequestContext) -> CreateUserResponse:
    if not request.email:
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

### Reading error details on the client

Error details are `google.protobuf.Any` messages that can be unpacked to their original types:

```python
try:
    response = await client.some_method(request)
except ConnectError as e:
    for detail in e.details:
        # Check the type before unpacking
        if detail.Is(Struct.DESCRIPTOR):
            unpacked = Struct()
            detail.Unpack(unpacked)
            print(f"Error detail: {unpacked}")
```

### Standard error detail types

With `googleapis-common-protos` installed, you can use standard types like:

- `BadRequest`: Field violations in a request
- `RetryInfo`: When to retry
- `Help`: Links to documentation
- `QuotaFailure`: Quota violations
- `ErrorInfo`: Structured error metadata

Example:

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

## HTTP representation

In the Connect protocol, errors are always JSON:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "code": "invalid_argument",
  "message": "name is required",
  "details": [
    {
      "type": "google.protobuf.Struct",
      "value": "base64-encoded-protobuf"
    }
  ]
}
```

The `details` array contains error detail messages, where each entry has:

- `type`: The fully-qualified protobuf message type (e.g., `google.protobuf.Struct`)
- `value`: The protobuf message serialized in binary format and then base64-encoded

## See also

- [Interceptors](interceptors.md) for error transformation and logging
- [Streaming](streaming.md) for stream-specific error handling
- [Headers and trailers](headers-and-trailers.md) for attaching metadata to errors
- [Usage guide](usage.md) for error handling best practices
