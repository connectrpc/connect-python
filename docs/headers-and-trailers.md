# Headers & trailers

To integrate with other systems, you may need to read or write custom HTTP headers with your RPCs.
For example, distributed tracing, authentication, authorization, and rate limiting often require
working with headers. Connect also supports trailers, which serve a similar purpose but can be written
after the response body. This document outlines how to work with headers and trailers.

## Headers

Connect headers are just HTTP headers - because Python's standard library does not provide a
corresponding type, we provide `request.Headers`. For most use cases, it is equivalent to a
dictionary while also providing additional methods to access multiple values for the same header
key when needed. Clients always accept a normal dictionary as well when accepting headers.

In services, headers are available on the `RequestContext`:

=== "ASGI"

    ```python
    class GreetService:
        async def greet(self, request, ctx):
            print(ctx.request_headers().get("acme-tenant-id"))
            ctx.response_headers()["greet-version"] = "v1"
            return GreetResponse()
    ```

=== "WSGI"

    ```python
    class GreetService:
        def greet(self, request, ctx):
            print(ctx.request_headers().get("acme-tenant-id"))
            ctx.response_headers()["greet-version"] = "v1"
            return GreetResponse()
    ```

For clients, we find that it is not common to read headers, but is fully supported.
To preserve client methods having simple signatures accepting and providing RPC
messages, headers are accessible through a separate context manager, `client.ResponseMetadata`.

=== "Async"

    ```python
    from connectrpc.client import ResponseMetadata

    client = GreetServiceClient("https://api.acme.com")
    with ResponseMetadata() as meta:
        res = await client.greet(GreetRequest(), headers={"acme-tenant-id": "1234"})
    print(meta.headers().get("greet-version"))
    ```

=== "Sync"

    ```python
    from connectrpc.client import ResponseMetadata

    client = GreetServiceClientSync("https://api.acme.com")
    with ResponseMetadata() as meta:
        res = client.greet(GreetRequest(), headers={"acme-tenant-id": "1234"})
    print(meta.headers().get("greet-version"))
    ```

Supported protocols require that header keys contain only ASCII letters, numbers, underscores, hyphens, and
periods, and the protocols reserve all keys beginning with "Connect-" or "Grpc-". Similarly, header values may
contain only printable ASCII and spaces. In our experience, application code writing reserved or non-ASCII headers
is unusual; rather than wrapping `request.Headers` in a fat validation layer, we rely on your good judgment.

## Trailers

Connect's APIs for manipulating response trailers work identically to headers. Trailers are most useful in
streaming handlers, which may need to send some metadata to the client after sending a few messages.
Unary handlers should nearly always use headers instead.

If you find yourself needing trailers, handlers and clients can access them much like headers:

=== "Async"

    ```python
    class GreetService:
        async def greet(self, request, ctx):
            ctx.response_trailers()["greet-version"] = "v1"
            return GreetResponse()

    client = GreetServiceClient("https://api.acme.com")
    with ResponseMetadata() as meta:
        res = await client.greet(GreetRequest(), headers={"acme-tenant-id": "1234"})
    print(meta.trailers().get("greet-version"))
    ```

=== "Sync"

    ```python
    class GreetService:
        def greet(self, request, ctx):
            ctx.response_trailers()["greet-version"] = "v1"
            return GreetResponse()

    client = GreetServiceClientSync("https://api.acme.com")
    with ResponseMetadata() as meta:
        res = client.greet(GreetRequest(), headers={"acme-tenant-id": "1234"})
    print(meta.trailers().get("greet-version"))
    ```
