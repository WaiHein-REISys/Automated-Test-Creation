"""
EHB2010 Test Runner - Python API for external tool integration.

Standalone module. Copy this file + parse_trx.py into your own project/repo.
No dependencies beyond Python stdlib and .NET SDK on the machine.

Usage:
    from ehb_test_runner import EHBTestRunner

    runner = EHBTestRunner(project_path="/path/to/EHB2010")

    # List available tags (from compiled tests)
    tags = runner.list_tags()

    # Run tests by tag
    result = runner.run(tag="Automated")
    result = runner.run(tag="SF424ShortApplicationCreation", run_id="myrun001")

    # Run with dotnet test filter expression
    result = runner.run(filter_expr="FullyQualifiedName~PriorApproval")

    # Check results
    print(result.passed, result.failed, result.total)
    print(result.exit_code)       # 0 = all passed
    print(result.trx_path)        # path to TRX file
    print(result.extent_report)   # path to ExtentReport HTML
    print(result.to_dict())       # full structured data

    # Iterate individual tests
    for test in result.tests:
        if test["outcome"] == "Failed":
            print(test["name"], test["error_message"])
"""

import os
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Optional

# parse_trx.py must be in the same directory or on PYTHONPATH
from parse_trx import parse_trx_file


@dataclass
class TestResult:
    """Structured result from a test run."""

    exit_code: int
    trx_path: str
    extent_report: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    outcome: str = "Unknown"
    start_time: str = ""
    end_time: str = ""
    tests: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return self.exit_code == 0 and self.failed == 0

    @property
    def failed_tests(self) -> list:
        return [t for t in self.tests if t["outcome"] == "Failed"]

    def to_dict(self) -> dict:
        return self.raw


class EHBTestRunner:
    """
    Orchestrates EHB2010 test execution from any location.

    Args:
        project_path: Absolute or relative path to the EHB2010 root directory.
        results_dir:  Where to write TRX files. Defaults to ./TestResults in CWD.
        config:       Build configuration (default: Release).
        auto_build:   Whether to build before running (default: True).
    """

    def __init__(
        self,
        project_path: str,
        results_dir: Optional[str] = None,
        config: str = "Release",
        auto_build: bool = True,
    ):
        self.project_path = os.path.abspath(project_path)
        project_suffix = os.path.basename(self.project_path)
        self.csproj = os.path.join(
            self.project_path,
            "EHB.UI.Automation",
            f"EHB.UI.Automation.{project_suffix}.csproj",
        )
        self.results_dir = os.path.abspath(results_dir or os.path.join(os.getcwd(), "TestResults"))
        self.config = config
        self.auto_build = auto_build

        if not os.path.isfile(self.csproj):
            raise FileNotFoundError(
                f"Cannot find {self.csproj}. "
                f"Make sure project_path points to the project root "
                f"(e.g. a directory ending in EHB2010, GPRSReview, etc.)."
            )

    def build(self) -> bool:
        """Build the project. Returns True on success."""
        result = subprocess.run(
            ["dotnet", "build", self.csproj, "--configuration", self.config, "--nologo", "-v", "q"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def run(
        self,
        tag: Optional[str] = None,
        filter_expr: Optional[str] = None,
        run_id: Optional[str] = None,
        quiet: bool = True,
        folders: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
    ) -> TestResult:
        """
        Execute tests and return structured results.

        Args:
            tag:          SpecFlow tag to filter by (e.g. "Automated", "SF424Short").
            filter_expr:  Raw dotnet test --filter expression (overrides tag).
            run_id:       Unique identifier for this run. Auto-generated if omitted.
            quiet:        Suppress dotnet test console output.
            folders:      Run only tests under these folders (relative to Features/).
                          E.g. ["GPRSReview", "PriorApproval/SF424Short"].
            files:        Run only tests from specific feature files (name or path).
                          E.g. ["SF424ShortApplicationCreation.feature"].

        Returns:
            TestResult with summary, individual test details, and file paths.
        """
        if run_id is None:
            run_id = uuid.uuid4().hex[:12]

        os.makedirs(self.results_dir, exist_ok=True)

        # Build if needed
        if self.auto_build:
            if not self.build():
                return TestResult(
                    exit_code=1,
                    trx_path="",
                    extent_report="",
                    outcome="BuildFailed",
                )

        # Construct filter
        effective_filter = filter_expr or (f"Category={tag}" if tag else "")

        # Build folder/file scope filter and combine with existing filter
        scope_filter = self._build_scope_filter(folders, files)
        if scope_filter:
            if effective_filter:
                effective_filter = f"({effective_filter}) & ({scope_filter})"
            else:
                effective_filter = scope_filter

        # Construct command
        trx_filename = f"TestResults_{run_id}.trx"
        cmd = [
            "dotnet", "test", self.csproj,
            "--configuration", self.config,
            "--no-build",
            "--nologo",
            "--logger", f"trx;LogFileName={trx_filename}",
            "--results-directory", self.results_dir,
        ]
        if effective_filter:
            cmd.extend(["--filter", effective_filter])

        # Run
        proc = subprocess.run(
            cmd,
            capture_output=quiet,
            text=True,
        )

        trx_path = os.path.join(self.results_dir, trx_filename)
        extent_report = os.path.join(
            self.project_path,
            "EHB.UI.Automation", "bin", self.config, "net8.0",
            "Reports", "ExtentReport.html",
        )

        # Parse TRX if it exists
        if os.path.isfile(trx_path):
            parsed = parse_trx_file(trx_path)
            summary = parsed.get("summary", {})
            return TestResult(
                exit_code=proc.returncode,
                trx_path=trx_path,
                extent_report=extent_report,
                total=summary.get("total", 0),
                passed=summary.get("passed", 0),
                failed=summary.get("failed", 0),
                outcome=summary.get("outcome", "Unknown"),
                start_time=summary.get("start_time", ""),
                end_time=summary.get("end_time", ""),
                tests=parsed.get("tests", []),
                raw=parsed,
            )
        else:
            return TestResult(
                exit_code=proc.returncode,
                trx_path=trx_path,
                extent_report=extent_report,
                outcome="NoTRXGenerated",
            )

    @staticmethod
    def _build_scope_filter(
        folders: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
    ) -> str:
        """Build a dotnet test filter from folder/file scope lists.

        Folders are matched via ``FullyQualifiedName~`` using the namespace
        segment that corresponds to the folder path (dots replace slashes).
        Files are matched by feature file name (without extension) as a
        namespace/class segment.
        """
        parts: list[str] = []

        if folders:
            for folder in folders:
                # Convert path separators to dots for namespace matching
                ns_segment = folder.replace("/", ".").replace("\\", ".").strip(".")
                parts.append(f"FullyQualifiedName~{ns_segment}")

        if files:
            for file in files:
                # Strip .feature extension and path separators for class name match
                name = os.path.basename(file)
                if name.endswith(".feature"):
                    name = name[: -len(".feature")]
                parts.append(f"FullyQualifiedName~{name}")

        if not parts:
            return ""

        # Combine with OR — run tests matching ANY of the specified scopes
        return " | ".join(parts)

    def list_tags(self) -> list[str]:
        """
        Scan feature files for all SpecFlow tags.
        Returns sorted list of tag names (without @).
        """
        import re

        features_dir = os.path.join(self.project_path, "EHB.UI.Automation", "Features")
        tags = set()
        tag_pattern = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")

        for root, _, files in os.walk(features_dir):
            for f in files:
                if f.endswith(".feature"):
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fh:
                            for line in fh:
                                tags.update(tag_pattern.findall(line))
                    except OSError:
                        pass

        return sorted(tags)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EHB2010 Test Runner CLI")
    parser.add_argument("--project", required=True, help="Path to EHB2010 root")
    parser.add_argument("--tag", help="SpecFlow tag to run")
    parser.add_argument("--filter", dest="filter_expr", help="dotnet test filter")
    parser.add_argument("--folder", action="append", default=[], help="Run tests under this folder (relative to Features/). Repeatable.")
    parser.add_argument("--file", action="append", default=[], dest="files", help="Run tests from this feature file. Repeatable.")
    parser.add_argument("--run-id", help="Unique run ID")
    parser.add_argument("--output", help="Results directory")
    parser.add_argument("--list-tags", action="store_true", help="List available tags and exit")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    runner = EHBTestRunner(
        project_path=args.project,
        results_dir=args.output,
    )

    if args.list_tags:
        for t in runner.list_tags():
            print(t)
        exit(0)

    result = runner.run(
        tag=args.tag,
        filter_expr=args.filter_expr,
        run_id=args.run_id,
        folders=args.folder or None,
        files=args.files or None,
    )

    if args.json:
        import json
        output = {
            "exit_code": result.exit_code,
            "trx_path": result.trx_path,
            "extent_report": result.extent_report,
            "all_passed": result.all_passed,
            "summary": {
                "outcome": result.outcome,
                "total": result.total,
                "passed": result.passed,
                "failed": result.failed,
            },
            "failed_tests": result.failed_tests,
        }
        print(json.dumps(output, indent=2))
    else:
        status = "PASSED" if result.all_passed else "FAILED"
        print(f"Result:  {status}")
        print(f"Total:   {result.total}  Passed: {result.passed}  Failed: {result.failed}")
        print(f"TRX:     {result.trx_path}")
        if result.failed_tests:
            print(f"\nFailed tests:")
            for t in result.failed_tests:
                print(f"  - {t['name']}")

    exit(result.exit_code)
