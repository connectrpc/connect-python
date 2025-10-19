# Testing

This guide covers testing connect-python services and clients.

## Setup

Install httpx for testing connect-python services and clients:

```bash
pip install httpx
# or: uv add --dev httpx
```

For pytest examples in this guide, you'll also need pytest (and pytest-asyncio for async tests). unittest requires no additional dependencies.

## Recommended approach: In-memory testing

The recommended approach is **in-memory testing** using httpx's ASGI/WSGI transports (provided by httpx, not connect-python). This tests your full application stack (routing, serialization, error handling, interceptors) while remaining fast and isolated - no network overhead or port conflicts.

Here's a minimal example without any test framework:

=== "ASGI"

    ```python
    import httpx
    from greet.v1.greet_connect import GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest
    from server import Greeter  # Your service implementation

    # Create ASGI app with your service
    app = GreetServiceASGIApplication(Greeter())

    # Connect client to service using in-memory transport
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"  # URL is ignored for in-memory transport
    ) as session:
        client = GreetServiceClient("http://test", session=session)
        response = await client.greet(GreetRequest(name="Alice"))

    print(response.greeting)  # "Hello, Alice!"
    ```

=== "WSGI"

    ```python
    import httpx
    from greet.v1.greet_connect import GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest
    from server import GreeterSync  # Your service implementation

    # Create WSGI app with your service
    app = GreetServiceWSGIApplication(GreeterSync())

    # Connect client to service using in-memory transport
    with httpx.Client(
        transport=httpx.WSGITransport(app=app),
        base_url="http://test"  # URL is ignored for in-memory transport
    ) as session:
        client = GreetServiceClientSync("http://test", session=session)
        response = client.greet(GreetRequest(name="Alice"))

    print(response.greeting)  # "Hello, Alice!"
    ```

This pattern works with any test framework (pytest, unittest) or none at all. The examples below show how to integrate with both pytest and unittest.

## Testing servers

### Using pytest

Testing the service we created in the [Getting Started](getting-started.md) guide looks like this:

=== "ASGI"

    ```python
    import httpx
    import pytest
    from greet.v1.greet_connect import GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest
    from server import Greeter  # Import your actual service implementation

    @pytest.mark.asyncio
    async def test_greet():
        # Create the ASGI application with your service
        app = GreetServiceASGIApplication(Greeter())

        # Test using httpx with ASGI transport
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)
            response = await client.greet(GreetRequest(name="Alice"))

        assert response.greeting == "Hello, Alice!"
    ```

=== "WSGI"

    ```python
    import httpx
    from greet.v1.greet_connect import GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest
    from server import GreeterSync  # Import your actual service implementation

    def test_greet():
        # Create the WSGI application with your service
        app = GreetServiceWSGIApplication(GreeterSync())

        # Test using httpx with WSGI transport
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)
            response = client.greet(GreetRequest(name="Alice"))

        assert response.greeting == "Hello, Alice!"
    ```

### Using unittest

The same in-memory testing approach works with unittest:

=== "ASGI"

    ```python
    import asyncio
    import httpx
    import unittest
    from greet.v1.greet_connect import GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest
    from server import Greeter

    class TestGreet(unittest.TestCase):
        def test_greet(self):
            async def run_test():
                app = GreetServiceASGIApplication(Greeter())
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test"
                ) as session:
                    client = GreetServiceClient("http://test", session=session)
                    response = await client.greet(GreetRequest(name="Alice"))
                    self.assertEqual(response.greeting, "Hello, Alice!")

            asyncio.run(run_test())
    ```

=== "WSGI"

    ```python
    import httpx
    import unittest
    from greet.v1.greet_connect import GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest
    from server import GreeterSync

    class TestGreet(unittest.TestCase):
        def test_greet(self):
            app = GreetServiceWSGIApplication(GreeterSync())
            with httpx.Client(
                transport=httpx.WSGITransport(app=app),
                base_url="http://test"
            ) as session:
                client = GreetServiceClientSync("http://test", session=session)
                response = client.greet(GreetRequest(name="Alice"))
                self.assertEqual(response.greeting, "Hello, Alice!")
    ```

This approach:

- Tests your full application stack (routing, serialization, error handling)
- Runs fast without network overhead
- Provides isolation between tests
- Works with all streaming types

For integration tests with actual servers over TCP/HTTP, see standard pytest patterns for [server fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html).

### Using fixtures for reusable test setup

For cleaner tests, use pytest fixtures to set up clients and services:

=== "ASGI"

    ```python
    import httpx
    import pytest
    import pytest_asyncio
    from greet.v1.greet_connect import GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest
    from server import Greeter

    @pytest_asyncio.fixture
    async def greet_client():
        app = GreetServiceASGIApplication(Greeter())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClient("http://test", session=session)

    @pytest.mark.asyncio
    async def test_greet(greet_client):
        response = await greet_client.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"

    @pytest.mark.asyncio
    async def test_greet_empty_name(greet_client):
        response = await greet_client.greet(GreetRequest(name=""))
        assert response.greeting == "Hello, !"
    ```

=== "WSGI"

    ```python
    import httpx
    import pytest
    from greet.v1.greet_connect import GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest
    from server import GreeterSync

    @pytest.fixture
    def greet_client():
        app = GreetServiceWSGIApplication(GreeterSync())
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClientSync("http://test", session=session)

    def test_greet(greet_client):
        response = greet_client.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"

    def test_greet_empty_name(greet_client):
        response = greet_client.greet(GreetRequest(name=""))
        assert response.greeting == "Hello, !"
    ```

This pattern:

- Reduces code duplication across multiple tests
- Makes tests more readable and focused on behavior
- Follows pytest best practices
- Matches the pattern used in connect-python's own test suite

With your test client setup, you can use any connect code for interacting with the service under test including [streaming](streaming.md), reading [headers and trailers](headers-and-trailers.md), or checking [errors](errors.md). For example, to test error handling:

```python
with pytest.raises(ConnectError) as exc_info:
    await client.greet(GreetRequest(name=""))

assert exc_info.value.code == Code.INVALID_ARGUMENT
```

See the [Errors](errors.md) guide for more details on error handling.


## Testing clients

For testing client code that calls Connect services, use the same in-memory testing approach shown above. Create a test service implementation and use httpx transports to test your client logic without network overhead.

### Example: Testing client error handling

=== "Async"

    ```python
    import pytest
    import httpx
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    async def fetch_user_greeting(user_id: str, client: GreetServiceClient):
        """Client code that handles errors."""
        try:
            response = await client.greet(GreetRequest(name=user_id))
            return response.greeting
        except ConnectError as e:
            if e.code == Code.NOT_FOUND:
                return "User not found"
            elif e.code == Code.UNAUTHENTICATED:
                return "Please login"
            raise

    @pytest.mark.asyncio
    async def test_client_error_handling():
        class TestGreetService(GreetService):
            async def greet(self, request, ctx):
                if request.name == "unknown":
                    raise ConnectError(Code.NOT_FOUND, "User not found")
                return GreetResponse(greeting=f"Hello, {request.name}!")

        app = GreetServiceASGIApplication(TestGreetService())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            # Test successful case
            result = await fetch_user_greeting("Alice", client)
            assert result == "Hello, Alice!"

            # Test error handling
            result = await fetch_user_greeting("unknown", client)
            assert result == "User not found"
    ```

=== "Sync"

    ```python
    import httpx
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    def fetch_user_greeting(user_id: str, client: GreetServiceClientSync):
        """Client code that handles errors."""
        try:
            response = client.greet(GreetRequest(name=user_id))
            return response.greeting
        except ConnectError as e:
            if e.code == Code.NOT_FOUND:
                return "User not found"
            elif e.code == Code.UNAUTHENTICATED:
                return "Please login"
            raise

    def test_client_error_handling():
        class TestGreetServiceSync(GreetServiceSync):
            def greet(self, request, ctx):
                if request.name == "unknown":
                    raise ConnectError(Code.NOT_FOUND, "User not found")
                return GreetResponse(greeting=f"Hello, {request.name}!")

        app = GreetServiceWSGIApplication(TestGreetServiceSync())
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            # Test successful case
            result = fetch_user_greeting("Alice", client)
            assert result == "Hello, Alice!"

            # Test error handling
            result = fetch_user_greeting("unknown", client)
            assert result == "User not found"
    ```

## Testing interceptors

Test interceptors as part of your full application stack. For example, testing the `ServerAuthInterceptor` from the [Interceptors](interceptors.md#metadata-interceptors) guide:

=== "ASGI"

    ```python
    import httpx
    import pytest
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest
    from interceptors import ServerAuthInterceptor
    from server import Greeter

    @pytest.mark.asyncio
    async def test_server_auth_interceptor():
        interceptor = ServerAuthInterceptor(["valid-token"])
        app = GreetServiceASGIApplication(
            Greeter(),
            interceptors=[interceptor]
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            # Valid token succeeds
            response = await client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer valid-token"}
            )
            assert response.greeting == "Hello, Alice!"

            # Invalid token format fails with UNAUTHENTICATED
            with pytest.raises(ConnectError) as exc_info:
                await client.greet(
                    GreetRequest(name="Bob"),
                    headers={"authorization": "invalid"}
                )
            assert exc_info.value.code == Code.UNAUTHENTICATED

            # Wrong token fails with PERMISSION_DENIED
            with pytest.raises(ConnectError) as exc_info:
                await client.greet(
                    GreetRequest(name="Bob"),
                    headers={"authorization": "Bearer wrong-token"}
                )
            assert exc_info.value.code == Code.PERMISSION_DENIED
    ```

=== "WSGI"

    ```python
    import httpx
    import pytest
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest
    from interceptors import ServerAuthInterceptor
    from server import GreeterSync

    def test_server_auth_interceptor():
        interceptor = ServerAuthInterceptor(["valid-token"])
        app = GreetServiceWSGIApplication(
            GreeterSync(),
            interceptors=[interceptor]
        )

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            # Valid token succeeds
            response = client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer valid-token"}
            )
            assert response.greeting == "Hello, Alice!"

            # Invalid token format fails with UNAUTHENTICATED
            with pytest.raises(ConnectError) as exc_info:
                client.greet(
                    GreetRequest(name="Bob"),
                    headers={"authorization": "invalid"}
                )
            assert exc_info.value.code == Code.UNAUTHENTICATED

            # Wrong token fails with PERMISSION_DENIED
            with pytest.raises(ConnectError) as exc_info:
                client.greet(
                    GreetRequest(name="Bob"),
                    headers={"authorization": "Bearer wrong-token"}
                )
            assert exc_info.value.code == Code.PERMISSION_DENIED
    ```

See the [Interceptors](interceptors.md) guide for more details on implementing interceptors.
