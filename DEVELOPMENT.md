# Development

## Setting Up Development Environment

### Prerequisites

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) for dependency management

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/connectrpc/connect-python
   cd connect-python
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

## Development Workflow

We use `poe` as a task runner. Available commands:

```bash
# Run all checks
uv run poe check

# Format code
uv run poe format

# Run tests
uv run poe test

# Run conformance tests
uv run poe test-conformance
```

## Code Style

We use:

- **ruff** for linting and formatting
- **pyright** for type checking
- **pytest** for testing

The project follows strict type checking and formatting standards.

## Testing

### Unit Tests

```bash
uv run poe test
```

### Conformance Tests

The project uses the official Connect conformance test suite. Go must be installed to run them.

```bash
uv run poe test-conformance
```

## Code Generation

The project includes protobuf code generation for examples and tests:

```bash
uv run poe generate
```

## Releasing

To release a new version, follow the guide in [RELEASE.md](./RELEASE.md).

## Documentation

Documentation is contained in the [connectrpc/connectrpc.com](https://github.com/connectrpc/connectrpc.com) repository.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the full smoke check suite: `uv run poe check`
5. Submit a pull request

### Pull Request Guidelines

- Ensure all tests pass
- Add tests for new functionality
- Update documentation as needed
- Follow the existing code style
- Write clear commit messages
