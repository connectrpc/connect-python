# Streaming

Connect supports several types of streaming RPCs. Streaming is exciting — it's fundamentally different from
the web's typical request-response model, and in the right circumstances it can be very efficient. If you've
been writing the same pagination or polling code for years, streaming may look like the answer to all your
problems.

Temper your enthusiasm. Streaming also comes with many drawbacks:

- It requires excellent HTTP libraries. At the very least, the client and server must be able to stream HTTP/1.1
  request and response bodies. For bidirectional streaming, both parties must support HTTP/2. Long-lived streams are
  much more likely to encounter bugs and edge cases in HTTP/2 flow control.

- It requires excellent proxies. Every proxy between the server and client — including those run by cloud providers —
  must support HTTP/2.

- It weakens the protections offered to your unary handlers, since streaming typically requires proxies to be
  configured with much longer timeouts.

- It requires complex tools. Streaming RPC protocols are much more involved than unary protocols, so cURL and your
  browser's network inspector are useless.

In general, streaming ties your application more closely to your networking infrastructure and makes your application
inaccessible to less-sophisticated clients. You can minimize these downsides by keeping streams short-lived.

All that said, `connect-python` fully supports client and server streaming. Bidirectional streaming is currently not
supported for clients and requires an HTTP/2 ASGI server for servers.

## Streaming variants

In Python, streaming messages use standard `AsyncIterator` for async servers and clients, or `Iterator` for sync servers
and clients.

In _client streaming_, the client sends multiple messages. Once the server receives all the messages, it responds with
a single message. In Protobuf schemas, client streaming methods look like this:

```protobuf
service GreetService {
  rpc Greet(stream GreetRequest) returns (GreetResponse) {}
}
```

In _server streaming_, the client sends a single message and the server responds with multiple messages. In Protobuf
schemas, server streaming methods look like this:

```protobuf
service GreetService {
  rpc Greet(GreetRequest) returns (stream GreetResponse) {}
}
```

In _bidirectional streaming_ (often called bidi), the client and server may both send multiple messages. Often, the
exchange is structured like a conversation: the client sends a message, the server responds, the client sends another
message, and so on. Keep in mind that this always requires end-to-end HTTP/2 support!

## HTTP representation

Streaming responses always have an HTTP status of 200 OK. This may seem unusual, but it's unavoidable: the server may
encounter an error after sending a few messages, when the HTTP status has already been sent to the client. Rather than
relying on the HTTP status, streaming handlers encode any errors in HTTP trailers or at the end of the response body.

The body of streaming requests and responses envelopes your schema-defined messages with a few bytes of
protocol-specific binary framing data. Because of the interspersed framing data, the payloads are no longer valid
Protobuf or JSON: instead, they use protocol-specific Content-Types like `application/connect+proto`.

## An example

Let's start by amending the `GreetService` we defined in [Getting Started](./getting-started.md) to make the Greet method use
client streaming:

```protobuf
syntax = "proto3";

package greet.v1;

message GreetRequest {
  string name = 1;
}

message GreetResponse {
  string greeting = 1;
}

service GreetService {
  rpc Greet(stream GreetRequest) returns (GreetResponse) {}
}
```

After running `buf generate` to update our generated code, we can amend our service implementation in
`server.py`:

=== "ASGI"

    ```python
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication
    from greet.v1.greet_pb2 import GreetResponse

    class Greeter(GreetService):
        async def greet(self, request, ctx):
            print("Request headers: ", ctx.request_headers())
            greeting = ""
            async for message in request:
                greeting += f"Hello, {message.name}!\n"
            response = GreetResponse(greeting=greeting)
            ctx.response_headers()["greet-version"] = "v1"
            return response

    app = GreetServiceASGIApplication(Greeter())
    ```

=== "WSGI"

    ```python
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication
    from greet.v1.greet_pb2 import GreetResponse

    class Greeter(GreetServiceSync):
        def greet(self, request, ctx):
            print("Request headers: ", ctx.request_headers())
            greeting = ""
            for message in request:
                greeting += f"Hello, {message.name}!\n"
            response = GreetResponse(greeting=f"Hello, {request.name}!")
            ctx.response_headers()["greet-version"] = "v1"
            return response

    app = GreetServiceWSGIApplication(Greeter())
    ```

That's it - metadata interceptors such as our [simple authentication interceptor](./interceptors.md#metadata-interceptors)
can be used as-is with no other changes.
