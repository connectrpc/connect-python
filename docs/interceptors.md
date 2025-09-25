# Interceptors

Interceptors are similar to the middleware or decorators you may be familiar with from other frameworks:
they're the primary way of extending Connect. They can modify the context, the request, the response,
and any errors. Interceptors are often used to add logging, metrics, tracing, retries, and other functionality.

Take care when writing interceptors! They're powerful, but overly complex interceptors can make debugging difficult.

## Interceptors are protocol implementations

Connect interceptors are protocol implementations with the same signature as an RPC handler, along with a
call_next `Callable` to continue with request processing. This allows writing interceptors in much the same
way as any handler, making sure to call `call_next` when needing to call business logic - or not, if overriding
the response within the interceptor itself.

Connect supports unary RPC and three stream types - because each has a different handler signature, we
provide protocols corresponding to each.

=== "ASGI"

    ```python
    class UnaryInterceptor(Protocol):

        async def intercept_unary(
            self,
            call_next: Callable[[REQ, RequestContext], Awaitable[RES]],
            request: REQ,
            ctx: RequestContext,
        ) -> RES: ...

    class ClientStreamInterceptor(Protocol):

        async def intercept_client_stream(
            self,
            call_next: Callable[[AsyncIterator[REQ], RequestContext], Awaitable[RES]],
            request: AsyncIterator[REQ],
            ctx: RequestContext,
        ) -> RES: ...

    class ServerStreamInterceptor(Protocol):

        def intercept_server_stream(
            self,
            call_next: Callable[[REQ, RequestContext], AsyncIterator[RES]],
            request: REQ,
            ctx: RequestContext,
        ) -> AsyncIterator[RES]: ...

    class BidiStreamInterceptor(Protocol):

        def intercept_bidi_stream(
            self,
            call_next: Callable[[AsyncIterator[REQ], RequestContext], AsyncIterator[RES]],
            request: AsyncIterator[REQ],
            ctx: RequestContext,
        ) -> AsyncIterator[RES]: ...
    ```

=== "WSGI"

    ```python
    class UnaryInterceptorSync(Protocol):

        def intercept_unary_sync(
            self,
            call_next: Callable[[REQ, RequestContext], RES],
            request: REQ,
            ctx: RequestContext,
        ) -> RES:

    class ClientStreamInterceptorSync(Protocol):

        def intercept_client_stream_sync(
            self,
            call_next: Callable[[Iterator[REQ], RequestContext], RES],
            request: Iterator[REQ],
            ctx: RequestContext,
        ) -> RES:

    class ServerStreamInterceptorSync(Protocol):

        def intercept_server_stream_sync(
            self,
            call_next: Callable[[REQ, RequestContext], Iterator[RES]],
            request: REQ,
            ctx: RequestContext,
        ) -> Iterator[RES]:

    class BidiStreamInterceptorSync(Protocol):

        def intercept_bidi_stream_sync(
            self,
            call_next: Callable[[Iterator[REQ], RequestContext], Iterator[RES]],
            request: Iterator[REQ],
            ctx: RequestContext,
        ) -> Iterator[RES]:
    ```

A single class can implement as many of the protocols as needed.

## An example

That's a little abstract, so let's consider an example: we'd like to apply a filter to our greeting
service from the [getting started documentation](./getting-started.md) that says goodbye instead of
hello to certain callers.

=== "ASGI"

    ```python
    class GoodbyeInterceptor:
        def __init__(self, users: list[str]):
            self._users = users

        async def intercept_unary(
            self,
            call_next: Callable[[GreetRequest, RequestContext], Awaitable[GreetResponse]],
            request: GreetRequest,
            ctx: RequestContext,
        ) -> GreetResponse:
            if request.name in self._users:
                return GreetResponse(greeting=f"Goodbye, {request.name}!")
            return await call_next(request, ctx)
    ```

=== "WSGI"

    ```python
    class GoodbyeInterceptor:
        def __init__(self, users: list[str]):
            self._users = users

        def intercept_unary_sync(
            self,
            call_next: Callable[[GreetRequest, RequestContext], GreetResponse],
            request: GreetRequest,
            ctx: RequestContext,
        ) -> GreetResponse:
            if request.name in self._users:
                return GreetResponse(greeting=f"Goodbye, {request.name}!")
            return call_next(request, ctx)
    ```

To apply our new interceptor to handlers, we can pass it to the application with `interceptors=`.

=== "ASGI"

    ```python
    app = GreetingServiceASGIApplication(service, interceptors=[GoodbyeInterceptor(["user1", "user2"])])
    ```

=== "WSGI"

    ```python
    app = GreetingServiceWSGIApplication(service, interceptors=[GoodbyeInterceptor(["user1", "user2"])])
    ```

Client constructors also accept an `interceptors=` parameter.

=== "Async"

    ```python
    client = GreetingServiceClient("http://localhost:8000", interceptors=[GoodbyeInterceptor(["user1", "user2"])])
    ```

=== "Sync"

    ```python
    client = GreetingServiceClientSync("http://localhost:8000", interceptors=[GoodbyeInterceptor(["user1", "user2"])])
    ```

## Metadata interceptors

Because the signature is different for each RPC type, we have an interceptor protocol for each
to be able to intercept RPC messages. However, many interceptors, such as for authentication or
tracing, only need access to headers and not messages. Connect provides a metadata interceptor
protocol that can be implemented to work with any RPC type.

An authentication interceptor checking bearer tokens may look like this:

=== "ASGI"

    ```python
    class AuthInterceptor:
        def __init__(self, valid_tokens: list[str]):
            self._valid_tokens = valid_tokens

        async def on_start(self, ctx: RequestContext):
            authorization = ctx.request_headers().get("authorization")
            if not authorization or not authorization.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED)
            token = authorization[len("Bearer "):]
            if token not in valid_tokens:
                raise ConnectError(Code.PERMISSION_DENIED)
    ```

=== "WSGI"

    ```python
    class AuthInterceptor:
        def __init__(self, valid_tokens: list[str]):
            self._valid_tokens = valid_tokens

        def on_start(self, ctx: RequestContext):
            authorization = ctx.request_headers().get("authorization")
            if not authorization or not authorization.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED)
            token = authorization[len("Bearer "):]
            if token not in valid_tokens:
                raise ConnectError(Code.PERMISSION_DENIED)
    ```

`on_start` can return any value, which is passed to the optional `on_end` method. This can be
used, for example, to record the time of execution for the method.

=== "ASGI"

    ```python
    import time

    class TimingInterceptor:
        async def on_start(self, ctx: RequestContext) -> float:
            return time.perf_counter()

        async def on_end(self, token: float, ctx: RequestContext):
            print(f"Method took {} seconds.", token - time.perf_counter())
    ```

=== "WSGI"

    ```python
    import time

    class TimingInterceptor:
        def on_start(self, ctx: RequestContext):
            return time.perf_counter()

        def on_end(self, token: float, ctx: RequestContext):
            print(f"Method took {} seconds.", token - time.perf_counter())
    ```
