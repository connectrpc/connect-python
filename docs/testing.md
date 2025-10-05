# Testing Guide

This guide covers testing connect-python services and clients.

> **Note:** The examples in this guide use a fictional `GreetService` for demonstration purposes. In your actual project, replace these with your own service definitions.

## Setup

Install the required testing dependencies:

```bash
pip install pytest pytest-asyncio httpx
```

Or if using uv:

```bash
uv add --dev pytest pytest-asyncio httpx
```

## Recommended approach: In-memory testing

The recommended approach is **in-memory testing** using httpx's ASGI/WSGI transports. This tests your full application stack (routing, serialization, error handling, interceptors) while remaining fast and isolated - no network overhead or port conflicts.

## Testing servers

### In-memory testing

Test services using httpx's ASGI/WSGI transport, which tests your full application stack while remaining fast and isolated:

=== "ASGI"

    ```python
    import pytest
    import httpx
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetService(GreetService):
        async def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.mark.asyncio
    async def test_greet():
        # Create the ASGI application
        app = GreetServiceASGIApplication(TestGreetService())

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
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    def test_greet():
        # Create the WSGI application
        app = GreetServiceWSGIApplication(TestGreetServiceSync())

        # Test using httpx with WSGI transport
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)
            response = client.greet(GreetRequest(name="Alice"))

        assert response.greeting == "Hello, Alice!"
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
    import pytest
    import pytest_asyncio
    import httpx
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetService(GreetService):
        async def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest_asyncio.fixture
    async def greet_client():
        app = GreetServiceASGIApplication(TestGreetService())
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
    async def test_greet_multiple_names(greet_client):
        response = await greet_client.greet(GreetRequest(name="Bob"))
        assert response.greeting == "Hello, Bob!"
    ```

=== "WSGI"

    ```python
    import pytest
    import httpx
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.fixture
    def greet_client():
        app = GreetServiceWSGIApplication(TestGreetServiceSync())
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClientSync("http://test", session=session)

    def test_greet(greet_client):
        response = greet_client.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"

    def test_greet_multiple_names(greet_client):
        response = greet_client.greet(GreetRequest(name="Bob"))
        assert response.greeting == "Hello, Bob!"
    ```

This pattern:

- Reduces code duplication across multiple tests
- Makes tests more readable and focused on behavior
- Follows pytest best practices
- Matches the pattern used in connect-python's own test suite

### Testing error handling

Test that your service returns appropriate errors:

=== "ASGI"

    ```python
    import pytest
    import httpx
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetService(GreetService):
        async def greet(self, request, ctx):
            if not request.name:
                raise ConnectError(Code.INVALID_ARGUMENT, "name is required")
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.mark.asyncio
    async def test_greet_error():
        app = GreetServiceASGIApplication(TestGreetService())

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            with pytest.raises(ConnectError) as exc_info:
                await client.greet(GreetRequest(name=""))

        assert exc_info.value.code == Code.INVALID_ARGUMENT
        assert "name is required" in exc_info.value.message
    ```

=== "WSGI"

    ```python
    import pytest
    import httpx
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class TestGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            if not request.name:
                raise ConnectError(Code.INVALID_ARGUMENT, "name is required")
            return GreetResponse(greeting=f"Hello, {request.name}!")

    def test_greet_error():
        app = GreetServiceWSGIApplication(TestGreetServiceSync())

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            with pytest.raises(ConnectError) as exc_info:
                client.greet(GreetRequest(name=""))

        assert exc_info.value.code == Code.INVALID_ARGUMENT
        assert "name is required" in exc_info.value.message
    ```

### Testing streaming services

For server streaming (assumes your service has a `greet_stream` method defined in your proto):

=== "ASGI"

    ```python
    @pytest.mark.asyncio
    async def test_server_streaming():
        class StreamingGreetService(GreetService):
            async def greet_stream(self, request, ctx):
                for i in range(3):
                    yield GreetResponse(greeting=f"Hello {request.name} #{i + 1}!")

        app = GreetServiceASGIApplication(StreamingGreetService())

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            responses = []
            async for response in client.greet_stream(GreetRequest(name="Alice")):
                responses.append(response)

        assert len(responses) == 3
        assert responses[0].greeting == "Hello Alice #1!"
    ```

=== "WSGI"

    ```python
    def test_server_streaming():
        class StreamingGreetServiceSync(GreetServiceSync):
            def greet_stream(self, request, ctx):
                for i in range(3):
                    yield GreetResponse(greeting=f"Hello {request.name} #{i + 1}!")

        app = GreetServiceWSGIApplication(StreamingGreetServiceSync())

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            responses = []
            for response in client.greet_stream(GreetRequest(name="Alice")):
                responses.append(response)

        assert len(responses) == 3
        assert responses[0].greeting == "Hello Alice #1!"
    ```

For client streaming (assumes your service has a `greet_many` method defined in your proto):

=== "ASGI"

    ```python
    @pytest.mark.asyncio
    async def test_client_streaming():
        class ClientStreamingService(GreetService):
            async def greet_many(self, request_stream, ctx):
                names = []
                async for req in request_stream:
                    names.append(req.name)
                return GreetResponse(greeting=f"Hello, {', '.join(names)}!")

        app = GreetServiceASGIApplication(ClientStreamingService())

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            async def request_stream():
                yield GreetRequest(name="Alice")
                yield GreetRequest(name="Bob")

            response = await client.greet_many(request_stream())

        assert "Alice" in response.greeting
        assert "Bob" in response.greeting
    ```

=== "WSGI"

    ```python
    def test_client_streaming():
        class ClientStreamingServiceSync(GreetServiceSync):
            def greet_many(self, request_stream, ctx):
                names = []
                for req in request_stream:
                    names.append(req.name)
                return GreetResponse(greeting=f"Hello, {', '.join(names)}!")

        app = GreetServiceWSGIApplication(ClientStreamingServiceSync())

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            def request_stream():
                yield GreetRequest(name="Alice")
                yield GreetRequest(name="Bob")

            response = client.greet_many(request_stream())

        assert "Alice" in response.greeting
        assert "Bob" in response.greeting
    ```

### Testing with context (headers and trailers)

Test code that uses request headers:

=== "ASGI"

    ```python
    class AuthGreetService(GreetService):
        async def greet(self, request, ctx):
            auth = ctx.request_headers().get("authorization")
            if not auth or not auth.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED, "Missing token")

            ctx.response_headers()["greet-version"] = "v1"
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.mark.asyncio
    async def test_greet_with_headers():
        app = GreetServiceASGIApplication(AuthGreetService())

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)

            response = await client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer token123"}
            )

        assert response.greeting == "Hello, Alice!"
    ```

=== "WSGI"

    ```python
    class AuthGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            auth = ctx.request_headers().get("authorization")
            if not auth or not auth.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED, "Missing token")

            ctx.response_headers()["greet-version"] = "v1"
            return GreetResponse(greeting=f"Hello, {request.name}!")

    def test_greet_with_headers():
        app = GreetServiceWSGIApplication(AuthGreetServiceSync())

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)

            response = client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer token123"}
            )

        assert response.greeting == "Hello, Alice!"
    ```


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

Test interceptors as part of your full application stack:

=== "ASGI"

    ```python
    class LoggingInterceptor:
        def __init__(self):
            self.requests = []

        async def on_start(self, ctx):
            method_name = ctx.method().name
            self.requests.append(method_name)
            return method_name

        async def on_end(self, token, ctx):
            # token is the value returned from on_start
            pass

    @pytest.mark.asyncio
    async def test_service_with_interceptor():
        interceptor = LoggingInterceptor()
        app = GreetServiceASGIApplication(
            TestGreetService(),
            interceptors=[interceptor]
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClient("http://test", session=session)
            await client.greet(GreetRequest(name="Alice"))

        # Verify interceptor was called
        assert "Greet" in interceptor.requests
    ```

=== "WSGI"

    ```python
    class LoggingInterceptorSync:
        def __init__(self):
            self.requests = []

        def on_start(self, ctx):
            method_name = ctx.method().name
            self.requests.append(method_name)
            return method_name

        def on_end(self, token, ctx):
            # token is the value returned from on_start
            pass

    def test_service_with_interceptor():
        interceptor = LoggingInterceptorSync()
        app = GreetServiceWSGIApplication(
            TestGreetServiceSync(),
            interceptors=[interceptor]
        )

        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            client = GreetServiceClientSync("http://test", session=session)
            client.greet(GreetRequest(name="Alice"))

        # Verify interceptor was called
        assert "Greet" in interceptor.requests
    ```

## Test organization

### Project structure

Organize your tests in a `test/` directory at the root of your project:

```
my-project/
├── greet/
│   └── v1/
│       ├── greet_connect.py
│       └── greet_pb2.py
├── test/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── test_greet.py        # Service tests
│   └── test_integration.py  # Integration tests
└── pyproject.toml
```

### Shared fixtures with conftest.py

Use `conftest.py` to share fixtures across multiple test files:

=== "ASGI"

    ```python
    # test/conftest.py
    import pytest
    import pytest_asyncio
    import httpx
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetResponse

    class TestGreetService(GreetService):
        async def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest_asyncio.fixture
    async def greet_client():
        """Shared client fixture available to all tests."""
        app = GreetServiceASGIApplication(TestGreetService())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClient("http://test", session=session)
    ```

    Then use it in any test file:

    ```python
    # test/test_greet.py
    import pytest
    from greet.v1.greet_pb2 import GreetRequest

    @pytest.mark.asyncio
    async def test_greet(greet_client):
        """Test basic greeting."""
        response = await greet_client.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"
    ```

=== "WSGI"

    ```python
    # test/conftest.py
    import pytest
    import httpx
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetResponse

    class TestGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.fixture
    def greet_client():
        """Shared client fixture available to all tests."""
        app = GreetServiceWSGIApplication(TestGreetServiceSync())
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClientSync("http://test", session=session)
    ```

    Then use it in any test file:

    ```python
    # test/test_greet.py
    from greet.v1.greet_pb2 import GreetRequest

    def test_greet(greet_client):
        """Test basic greeting."""
        response = greet_client.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"
    ```

### Running tests

Run all tests:

```bash
pytest
```

Run tests in a specific file:

```bash
pytest test/test_greet.py
```

Run a specific test:

```bash
pytest test/test_greet.py::test_greet
```

Run with verbose output:

```bash
pytest -v
```

## Practical examples

### Testing with mock external dependencies

Use fixtures to mock external services:

=== "ASGI"

    ```python
    import pytest
    import pytest_asyncio
    from unittest.mock import AsyncMock
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class DatabaseGreetService(GreetService):
        def __init__(self, db):
            self.db = db

        async def greet(self, request, ctx):
            # Fetch greeting from database
            greeting_template = await self.db.get_greeting_template()
            return GreetResponse(greeting=greeting_template.format(name=request.name))

    @pytest.fixture
    def mock_db():
        """Mock database for testing."""
        db = AsyncMock()
        db.get_greeting_template.return_value = "Hello, {name}!"
        return db

    @pytest_asyncio.fixture
    async def greet_client_with_db(mock_db):
        app = GreetServiceASGIApplication(DatabaseGreetService(mock_db))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClient("http://test", session=session)

    @pytest.mark.asyncio
    async def test_greet_with_database(greet_client_with_db, mock_db):
        response = await greet_client_with_db.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"
        mock_db.get_greeting_template.assert_called_once()
    ```

=== "WSGI"

    ```python
    import pytest
    from unittest.mock import Mock
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class DatabaseGreetServiceSync(GreetServiceSync):
        def __init__(self, db):
            self.db = db

        def greet(self, request, ctx):
            # Fetch greeting from database
            greeting_template = self.db.get_greeting_template()
            return GreetResponse(greeting=greeting_template.format(name=request.name))

    @pytest.fixture
    def mock_db():
        """Mock database for testing."""
        db = Mock()
        db.get_greeting_template.return_value = "Hello, {name}!"
        return db

    @pytest.fixture
    def greet_client_with_db(mock_db):
        app = GreetServiceWSGIApplication(DatabaseGreetServiceSync(mock_db))
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClientSync("http://test", session=session)

    def test_greet_with_database(greet_client_with_db, mock_db):
        response = greet_client_with_db.greet(GreetRequest(name="Alice"))
        assert response.greeting == "Hello, Alice!"
        mock_db.get_greeting_template.assert_called_once()
    ```

### Testing authentication flows

Test services that require authentication:

=== "ASGI"

    ```python
    import pytest
    import pytest_asyncio
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetService, GreetServiceASGIApplication, GreetServiceClient
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class AuthGreetService(GreetService):
        async def greet(self, request, ctx):
            # Check for authorization header
            auth = ctx.request_headers().get("authorization")
            if not auth or not auth.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED, "Missing or invalid token")

            # Validate token (simplified)
            token = auth[7:]  # Remove "Bearer " prefix
            if token != "valid-token":
                raise ConnectError(Code.UNAUTHENTICATED, "Invalid token")

            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest_asyncio.fixture
    async def auth_greet_client():
        app = GreetServiceASGIApplication(AuthGreetService())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClient("http://test", session=session)

    @pytest.mark.asyncio
    async def test_greet_with_valid_token(auth_greet_client):
        response = await auth_greet_client.greet(
            GreetRequest(name="Alice"),
            headers={"authorization": "Bearer valid-token"}
        )
        assert response.greeting == "Hello, Alice!"

    @pytest.mark.asyncio
    async def test_greet_without_token(auth_greet_client):
        with pytest.raises(ConnectError) as exc_info:
            await auth_greet_client.greet(GreetRequest(name="Alice"))

        assert exc_info.value.code == Code.UNAUTHENTICATED
        assert "Missing or invalid token" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_greet_with_invalid_token(auth_greet_client):
        with pytest.raises(ConnectError) as exc_info:
            await auth_greet_client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer invalid-token"}
            )

        assert exc_info.value.code == Code.UNAUTHENTICATED
        assert "Invalid token" in exc_info.value.message
    ```

=== "WSGI"

    ```python
    import pytest
    from connectrpc.code import Code
    from connectrpc.errors import ConnectError
    from greet.v1.greet_connect import GreetServiceSync, GreetServiceWSGIApplication, GreetServiceClientSync
    from greet.v1.greet_pb2 import GreetRequest, GreetResponse

    class AuthGreetServiceSync(GreetServiceSync):
        def greet(self, request, ctx):
            # Check for authorization header
            auth = ctx.request_headers().get("authorization")
            if not auth or not auth.startswith("Bearer "):
                raise ConnectError(Code.UNAUTHENTICATED, "Missing or invalid token")

            # Validate token (simplified)
            token = auth[7:]  # Remove "Bearer " prefix
            if token != "valid-token":
                raise ConnectError(Code.UNAUTHENTICATED, "Invalid token")

            return GreetResponse(greeting=f"Hello, {request.name}!")

    @pytest.fixture
    def auth_greet_client():
        app = GreetServiceWSGIApplication(AuthGreetServiceSync())
        with httpx.Client(
            transport=httpx.WSGITransport(app=app),
            base_url="http://test"
        ) as session:
            yield GreetServiceClientSync("http://test", session=session)

    def test_greet_with_valid_token(auth_greet_client):
        response = auth_greet_client.greet(
            GreetRequest(name="Alice"),
            headers={"authorization": "Bearer valid-token"}
        )
        assert response.greeting == "Hello, Alice!"

    def test_greet_without_token(auth_greet_client):
        with pytest.raises(ConnectError) as exc_info:
            auth_greet_client.greet(GreetRequest(name="Alice"))

        assert exc_info.value.code == Code.UNAUTHENTICATED
        assert "Missing or invalid token" in exc_info.value.message

    def test_greet_with_invalid_token(auth_greet_client):
        with pytest.raises(ConnectError) as exc_info:
            auth_greet_client.greet(
                GreetRequest(name="Alice"),
                headers={"authorization": "Bearer invalid-token"}
            )

        assert exc_info.value.code == Code.UNAUTHENTICATED
        assert "Invalid token" in exc_info.value.message
    ```
