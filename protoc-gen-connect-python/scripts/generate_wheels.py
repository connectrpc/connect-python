from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    base_dir = Path(__file__).parent / ".." / ".."
    with (base_dir / "out" / "artifacts.json").open() as f:
        artifacts: list[dict[str, str]] = json.load(f)
    for artifact in artifacts:
        if artifact["type"] != "Binary":
            continue
        # Check https://go.dev/wiki/MinimumRequirements#operating-systems for
        # minimum OS versions, especially MacOS
        platform = ""
        match artifact["goos"]:
            case "darwin":
                match artifact["goarch"]:
                    case "amd64":
                        platform = "macosx_11_0_x86_64"
                    case "arm64":
                        platform = "macosx_11_0_arm64"
            case "linux":
                match artifact["goarch"]:
                    case "amd64":
                        platform = "manylinux_2_17_x86_64.manylinux2014_x86_64.musllinux_1_1_x86_64"
                    case "arm64":
                        platform = "manylinux_2_17_aarch64.manylinux2014_aarch64.musllinux_1_1_aarch64"
            case "windows":
                match artifact["goarch"]:
                    case "amd64":
                        platform = "win_amd64"
                    case "arm64":
                        platform = "win_arm64"
        if not platform:
            msg = f"Unsupported platform: {artifact['goos']}/{artifact['goarch']}"
            raise ValueError(msg)
        exe_path = base_dir / artifact["path"]
        bin_dir = Path(__file__).parent / ".." / "out" / "bin"
        shutil.rmtree(bin_dir, ignore_errors=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe_path, bin_dir / exe_path.name)
        subprocess.run(["uv", "build", "--wheel"], check=True)  # noqa: S607
        dist_dir = Path(__file__).parent / ".." / "dist"
        built_wheel = next(dist_dir.glob("*-py3-none-any.whl"))

        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "wheel",
                "tags",
                "--remove",
                "--platform-tag",
                platform,
                built_wheel,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
