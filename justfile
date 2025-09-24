BUF_VERSION := "v1.57.0"

[private]
@default: check

format:
    uv run ruff check --fix .
    uv run ruff format .

lint:
    uv run ruff format --check .
    uv run ruff check .

typecheck:
    uv run pyright

[working-directory: 'noextras']
test-noextras *args:
    uv run --exact pytest {{args}}

test *args: (test-noextras args)
    uv run pytest {{args}}

check: lint typecheck test

[working-directory: 'conformance']
conformance *args:
    uv run pytest {{args}}

docs:
    uv run mkdocs build

[working-directory: 'site']
docs-serve: docs
    uv run python -m http.server 8000

[working-directory: 'conformance']
generate-conformance:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate
    @# We use the published conformance protos for tests, but need to make sure their package doesn't start with connectrpc
    @# which conflicts with the runtime package. Since protoc python plugin does not provide a way to change the package
    @# structure, we use sed to fix the imports instead.
    LC_ALL=c find test/gen -type f -exec sed -i '' 's/from connectrpc.conformance.v1/from gen.connectrpc.conformance.v1/' {} +

[working-directory: 'example']
generate-example:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate

[working-directory: 'test']
generate-test:
    go run github.com/bufbuild/buf/cmd/buf@{{BUF_VERSION}} generate

generate: generate-conformance generate-example generate-test format
