"""Build the Zig renderer once when producing a platform wheel."""

from __future__ import annotations

import platform
import subprocess
import sysconfig
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    @staticmethod
    def _library_name() -> str:
        system = platform.system()
        if system == "Linux":
            return "libzanim_core.so"
        if system == "Darwin":
            return "libzanim_core.dylib"
        if system == "Windows":
            return "zanim_core.dll"
        raise RuntimeError(f"unsupported wheel platform: {system} {platform.machine()}")

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        subprocess.run(
            ["zig", "build", "-Doptimize=ReleaseFast"],
            cwd=root,
            check=True,
        )
        name = self._library_name()
        artifact_dir = "bin" if platform.system() == "Windows" else "lib"
        built = root / "zig-out" / artifact_dir / name
        if not built.is_file():
            raise RuntimeError(f"Zig build did not produce {built}")
        build_data["force_include"][str(built)] = f"zanim/_native/{name}"
        # The wheel contains native code loaded through ctypes and must never be
        # advertised as a platform-independent py3-none-any artifact.
        build_data["pure_python"] = False
        platform_tag = sysconfig.get_platform().replace("-", "_").replace(".", "_")
        build_data["tag"] = f"py3-none-{platform_tag}"
