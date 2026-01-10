from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ._util import VERSION_CONFORMANCE, maybe_patch_args_with_debug

_current_dir = Path(__file__).parent
_client_py_path = str(_current_dir / "client.py")
_config_path = str(_current_dir / "config.yaml")

_skipped_tests_sync = [
    # Need to use async APIs for proper cancellation support in Python.
    "--skip",
    "Client Cancellation/**",
]

_httpx_opts = [
    # Trailers not supported
    "--skip",
    "**/Protocol:PROTOCOL_GRPC/**",
    "--skip",
    "gRPC Trailers/**",
    "--skip",
    "gRPC Unexpected Responses/**",
    "--skip",
    "gRPC Empty Responses/**",
    "--skip",
    "gRPC Proto Sub-Format Responses/**",
    # Bidirectional streaming not supported
    "--skip",
    "**/full-duplex/**",
    # Cancellation delivery isn't reliable
    "--known-flaky",
    "Client Cancellation/**",
    "--known-flaky",
    "Timeouts/**",
]


@pytest.mark.parametrize("client", ["httpx", "pyqwest"])
def test_client_sync(client: str) -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "sync", "--client", client]
    )

    opts = []
    match client:
        case "httpx":
            opts = _httpx_opts

    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "client",
            *opts,
            *_skipped_tests_sync,
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


@pytest.mark.parametrize("client", ["httpx", "pyqwest"])
def test_client_async(client: str) -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "async", "--client", client]
    )

    opts = []
    match client:
        case "httpx":
            opts = _httpx_opts

    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "client",
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
