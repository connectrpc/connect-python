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


def test_client_sync() -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "sync"]
    )
    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "client",
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


_skipped_tests_async = [
    # Cancellation currently not working for full duplex
    "--skip",
    "Client Cancellation/**/full-duplex/**",
]


def test_client_async() -> None:
    args = maybe_patch_args_with_debug(
        [sys.executable, _client_py_path, "--mode", "async"]
    )
    result = subprocess.run(
        [
            "go",
            "run",
            f"connectrpc.com/conformance/cmd/connectconformance@{VERSION_CONFORMANCE}",
            "--conf",
            _config_path,
            "--mode",
            "client",
            *_skipped_tests_async,
            "--known-flaky",
            "Client Cancellation/**",
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
