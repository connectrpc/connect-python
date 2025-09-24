# https://just.systems/

BUF_VERSION := "v1.57.0"

[private]
@default: check

# Format Python files
format:
    uv run ruff check --fix .
    uv run ruff format .

# Lint Python files
lint:
    uv run ruff format --check .
    uv run ruff check .

# Typecheck Python files
typecheck:
    uv run pyright

# Run unit tests with no extras
[working-directory: 'noextras']
test-noextras *args:
    uv run --exact pytest {{args}}

# Run unit tests
test *args: (test-noextras args)
    uv run pytest {{args}}

# Run lint, typecheck and test
check: lint typecheck test

# Run conformance tests
[working-directory: 'conformance']
conformance *args:
    uv run pytest {{args}}

# Build docs
docs:
    uv run mkdocs build

# Serve the docs locally
[working-directory: 'site']
docs-serve: docs
    uv run python -m http.server 8000

# Generate conformance files
[working-directory: 'conformance']
generate-conformance:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate
    @# We use the published conformance protos for tests, but need to make sure their package doesn't start with connectrpc
    @# which conflicts with the runtime package. Since protoc python plugin does not provide a way to change the package
    @# structure, we use sed to fix the imports instead.
    LC_ALL=c find test/gen -type f -exec sed -i '' 's/from connectrpc.conformance.v1/from gen.connectrpc.conformance.v1/' {} +

# Generate example files
[working-directory: 'example']
generate-example:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate

# Generate test files
[working-directory: 'test']
generate-test:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate

# Run all generation targets, and format the generated code
generate: generate-conformance generate-example generate-test format

# Used in CI to verify that `just generate` doesn't produce a diff
checkgenerate: generate
	test -z "$$(git status --porcelain | tee /dev/stderr)"
