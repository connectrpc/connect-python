import subprocess
import sys
from pathlib import Path

import pytest

from ._util import VERSION_CONFORMANCE, maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_server_py_path = str(_current_dir / "server.py")
_config_path = str(_current_dir / "config.yaml")


# Servers often run out of file descriptors on macOS due to low default ulimit.
# We go ahead and raise it automatically so tests can pass without special
# configuration.
@pytest.fixture(autouse=True, scope="session")
def macos_raise_ulimit():
    if sys.platform == "darwin":
        import resource  # noqa: PLC0415

        resource.setrlimit(resource.RLIMIT_NOFILE, (16384, 16384))


@pytest.mark.parametrize("server", ["granian", "gunicorn", "hypercorn"])
def test_server_sync(server: str) -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _server_py_path, "--mode", "sync", "--server", server]
    )
    opts = [
        # While Hypercorn and Granian supports HTTP/2 and WSGI, they both have simple wrappers
        # that reads the entire request body before running the application, which does not work for
        # full duplex. There are no other popular WSGI servers that support HTTP/2, so in practice
        # it cannot be supported. It is possible in theory following hyper-h2's example code in
        # https://python-hyper.org/projects/hyper-h2/en/stable/wsgi-example.html though.
        "--skip",
        "**/bidi-stream/full-duplex/**",
    ]
    match server:
        case "gunicorn":
            # gunicorn doesn't support HTTP/2
            opts = ["--skip", "**/HTTPVersion:2/**"]

    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "server",
            *opts,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


@pytest.mark.parametrize("server", ["granian", "hypercorn", "uvicorn"])
def test_server_async(server: str) -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _server_py_path, "--mode", "async", "--server", server]
    )
    opts = []
    match server:
        case "uvicorn":
            # uvicorn doesn't support HTTP/2
            opts = ["--skip", "**/HTTPVersion:2/**"]
    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "server",
            *opts,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
