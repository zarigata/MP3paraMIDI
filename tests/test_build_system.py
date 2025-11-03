import ast
import os
import shutil
import subprocess
import sys
from importlib import import_module
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestBuildSystem:
    """Smoke tests to ensure build configuration files exist and are valid."""

    def test_spec_files_exist(self):
        spec_standard = PROJECT_ROOT / "build_configs" / "mp3paramidi.spec"
        spec_ai = PROJECT_ROOT / "build_configs" / "mp3paramidi-ai.spec"
        assert spec_standard.exists(), "Standard spec file is missing"
        assert spec_ai.exists(), "AI spec file is missing"

    def test_icon_scripts_exist(self):
        sh_script = PROJECT_ROOT / "tools" / "build_icons.sh"
        ps_script = PROJECT_ROOT / "tools" / "build_icons.ps1"
        assert sh_script.exists(), "POSIX icon build script missing"
        assert ps_script.exists(), "PowerShell icon build script missing"

    def test_icon_master_exists(self):
        master_svg = PROJECT_ROOT / "assets" / "master.svg"
        assert master_svg.exists(), "Master SVG icon source missing"

    @pytest.mark.skipif(shutil.which("desktop-file-validate") is None, reason="desktop-file-validate not installed")
    def test_desktop_file_valid(self):
        desktop_file = PROJECT_ROOT / "build_configs" / "linux" / "mp3paramidi.desktop"
        assert desktop_file.exists(), "Desktop file missing"
        subprocess.run(["desktop-file-validate", str(desktop_file)], check=True)

    @pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX executable bit not supported on Windows")
    def test_apprun_executable(self):
        apprun = PROJECT_ROOT / "build_configs" / "linux" / "AppRun"
        assert apprun.exists(), "AppRun script missing"
        assert os.access(apprun, os.X_OK), "AppRun script is not executable"

    def test_version_consistency(self):
        versions = {}

        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if pyproject_path.exists():
            try:
                try:
                    import tomllib  # type: ignore[attr-defined]
                except ModuleNotFoundError:  # Python < 3.11
                    import tomli as tomllib  # type: ignore[no-redef]
                pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
                project_version = pyproject_data.get("project", {}).get("version")
                if project_version:
                    versions["pyproject"] = project_version
            except Exception as exc:  # pragma: no cover - defensive guard
                pytest.fail(f"Failed parsing pyproject.toml: {exc}")

        try:
            package_version = importlib_metadata.version("mp3paramidi")
            versions["package"] = package_version
        except importlib_metadata.PackageNotFoundError:
            pass

        try:
            module_version = import_module("mp3paramidi").__version__  # type: ignore[attr-defined]
            versions["module"] = module_version
        except (AttributeError, ModuleNotFoundError):
            pass

        main_window_path = PROJECT_ROOT / "src" / "mp3paramidi" / "gui" / "main_window.py"
        if main_window_path.exists():
            for line in main_window_path.read_text(encoding="utf-8").splitlines():
                if "setApplicationVersion" in line:
                    candidate = line.split("(")[-1].rstrip(")")
                    stripped = candidate.strip().strip('"\' )
                    if stripped and stripped[0].isdigit():
                        versions["ui"] = stripped
                        break

        if len(versions) < 2:
            pytest.skip("Insufficient version sources to compare")

        assert len(set(versions.values())) == 1, f"Version numbers are inconsistent: {versions}"

    def test_github_workflow_syntax(self):
        workflow = PROJECT_ROOT / ".github" / "workflows" / "build.yml"
        assert workflow.exists(), "build.yml workflow missing"
        yaml.safe_load(workflow.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("spec_path", [
        PROJECT_ROOT / "build_configs" / "mp3paramidi.spec",
        PROJECT_ROOT / "build_configs" / "mp3paramidi-ai.spec",
    ])
    def test_spec_file_syntax(self, spec_path):
        ast.parse(spec_path.read_text(encoding="utf-8"))
