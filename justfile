# Run all checks (format, check, mypy, integration-test)
all: format check mypy integration-test

# Run mypy type checking
mypy: mypy-package mypy-tests

mypy-package:
    mypy --package connectrpc

mypy-tests:
    MYPYPATH=tests/conformance mypy --module conformance_client --module conformance --module conformance_server --module connectrpc.conformance.v1.service_pb2_connect

# Format code with ruff
format:
    ruff format src tests examples

# Check code with ruff linter
check:
    ruff check src tests examples

# Fix auto-fixable ruff linter issues
fix:
    ruff check src tests examples --fix

# Run tests
# NOTE: Fails currently, as there are no unit tests within tests/.
test:
    pytest

# Run integration test against demo.connectrpc.com
integration-test:
    cd examples && python eliza_async_integration_test.py --protocols connect-proto connect-json

# Run protoc with connect_python plugin (development mode). usage: uv run just protoc-gen [PROTOC_ARGS...]
protoc-gen *ARGS:
    protoc --plugin=protoc-gen-connect_python=.venv/bin/protoc-gen-connect_python {{ ARGS }}

generate:
    cd tests/conformance && buf generate
    cd examples && buf generate

# Run conformance tests
conformance-test: conformance-test-client-async conformance-test-client-sync conformance-test-server-sync

# Run conformance tests of async client implementation
conformance-test-client-async *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v connectconformance &> /dev/null; then
        echo "Error: connectconformance binary not found in PATH"
        echo "Please install it with: go install connectrpc.com/conformance/cmd/connectconformance@latest"
        echo "Or download from: https://github.com/connectrpc/conformance/releases"
        exit 1
    fi
    cd tests/conformance

    connectconformance \
        --conf ./async_config.yaml \
        --mode client \
        --known-failing="Client Cancellation/**" \
        {{ ARGS }} \
        -- \
        python conformance_client.py async

# Run conformance tests of sync client implementation
conformance-test-client-sync *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v connectconformance &> /dev/null; then
        echo "Error: connectconformance binary not found in PATH"
        echo "Please install it with: go install connectrpc.com/conformance/cmd/connectconformance@latest"
        echo "Or download from: https://github.com/connectrpc/conformance/releases"
        exit 1
    fi
    cd tests/conformance

    connectconformance \
        --conf ./sync_config.yaml \
        --mode client \
        --known-failing="Client Cancellation/**" \
        {{ ARGS }} \
        -- \
        python conformance_client.py sync

# Run conformance tests of sync server implementation
conformance-test-server-sync *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v connectconformance &> /dev/null; then
        echo "Error: connectconformance binary not found in PATH"
        echo "Please install it with: go install connectrpc.com/conformance/cmd/connectconformance@latest"
        echo "Or download from: https://github.com/connectrpc/conformance/releases"
        exit 1
    fi
    cd tests/conformance

    connectconformance \
        --conf ./sync_server_config.yaml \
        --mode server \
        {{ ARGS }} \
        -- \
        python conformance_server.py sync

# Clean all cache files and rebuild environment
clean:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Cleaning Python bytecode cache..."
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    echo "Cleaning mypy cache..."
    rm -rf .mypy_cache
    echo "Recreating virtual environment..."
    rm -rf .venv
    uv sync --group dev --all-extras
    echo "Clean complete!"

# Build documentation
docs:
    cd docs && sphinx-build -b html . _build/html

# Serve documentation locally
docs-serve: docs
    cd docs/_build/html && python -m http.server 8000

# Clean documentation build
docs-clean:
    rm -rf docs/_build
