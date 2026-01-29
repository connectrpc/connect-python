from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ._util import VERSION_CONFORMANCE, coverage_env, maybe_patch_args_with_debug

if TYPE_CHECKING:
    from coverage import Coverage

_current_dir = Path(__file__).parent
_client_py_path = str(_current_dir / "client.py")
_config_path = str(_current_dir / "config.yaml")

_skipped_tests_sync = [
    # Need to use async APIs for proper cancellation support in Python.
    "--skip",
    "Client Cancellation/**",
]


def test_client_sync(cov: Coverage | None) -> None:
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
        env=coverage_env(cov),
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")


def test_client_async(cov: Coverage | None) -> None:
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
            "--",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=coverage_env(cov),
    )
    if result.returncode != 0:
        pytest.fail(f"\n{result.stdout}\n{result.stderr}")
