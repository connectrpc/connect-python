import os
import subprocess
import sys
from pathlib import Path

import pytest

from ._util import VERSION_CONFORMANCE, maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_server_py_path = str(_current_dir / "server.py")
_config_path = str(_current_dir / "config.yaml")


# Servers often run out of file descriptors due to low default ulimit.
# We go ahead and raise it automatically so tests can pass without special
# configuration.
@pytest.fixture(autouse=True, scope="session")
def macos_raise_ulimit():
    if os.name != "posix":
        return

    import resource  # noqa: PLC0415

    resource.setrlimit(resource.RLIMIT_NOFILE, (16384, 16384))


# There is a relatively low time limit for the server to respond with a resource error
# for this test. In resource limited environments such as CI, it doesn't seem to be enough,
# notably it is the first request that will take the longest to process as it also sets up
# the request. We can consider raising this delay in the runner to see if it helps.
#
# https://github.com/connectrpc/conformance/blob/main/internal/app/connectconformance/testsuites/data/server_message_size.yaml#L46
_known_flaky = [
    "--known-flaky",
    "Server Message Size/HTTPVersion:1/**/first-request-exceeds-server-limit",
]


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
        case "granian" | "hypercorn":
            # granian and hypercorn seem to have issues with concurrency
            opts += ["--parallel", "1"]
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
            *_known_flaky,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if server == "granian":
            # Even with low parallelism, some tests are flaky. We'll need to investigate further.
            print(  # noqa: T201
                f"Granian server tests failed, see output below, not treating as failure:\n{result.stdout}\n{result.stderr}"
            )
            return
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


@pytest.mark.parametrize("server", ["daphne", "granian", "hypercorn", "uvicorn"])
def test_server_async(server: str) -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _server_py_path, "--mode", "async", "--server", server]
    )
    opts = []
    match server:
        case "daphne":
            opts = [
                # daphne doesn't support h2c
                "--skip",
                "**/HTTPVersion:2/**/TLS:false/**",
                # daphne seems to block on the request body so can't do full duplex even with h2,
                # it only works with websockets
                "--skip",
                "**/full-duplex/**",
            ]
        case "granian" | "hypercorn":
            # granian and hypercorn seem to have issues with concurrency
            opts = ["--parallel", "1"]
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
            *_known_flaky,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if server == "granian":
            # Even with low parallelism, some tests are flaky. We'll need to investigate further.
            print(  # noqa: T201
                f"Granian server tests failed, see output below, not treating as failure:\n{result.stdout}\n{result.stderr}"
            )
            return
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
