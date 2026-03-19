"""
TRX Result Parser (Standalone)

Parses .trx (Visual Studio Test Results) files into structured data.
No external dependencies — uses only Python stdlib.
Can be used from any location; just import or call directly.

CLI usage:
    python parse_trx.py <path-to-trx-file>
    python parse_trx.py <path-to-trx-file> --format json
    python parse_trx.py <path-to-trx-file> --format summary

Programmatic usage:
    from parse_trx import parse_trx_file
    result = parse_trx_file("/any/path/to/TestResults.trx")
    print(result["summary"]["passed"])
    for test in result["tests"]:
        print(test["name"], test["outcome"], test["duration_ms"])
"""

import xml.etree.ElementTree as ET
import json
import sys
import os

# TRX XML namespace
NS = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


def parse_trx_file(trx_path: str) -> dict:
    """
    Parse a TRX file and return structured results.

    Args:
        trx_path: Absolute or relative path to a .trx file.

    Returns:
        Dict with keys: file, summary, tests.
    """
    trx_path = os.path.abspath(trx_path)
    tree = ET.parse(trx_path)
    root = tree.getroot()

    # --- Summary counters ---
    counters_el = root.find(".//trx:ResultSummary/trx:Counters", NS)
    summary = {}
    if counters_el is not None:
        summary = {
            "total": int(counters_el.get("total", 0)),
            "passed": int(counters_el.get("passed", 0)),
            "failed": int(counters_el.get("failed", 0)),
            "error": int(counters_el.get("error", 0)),
            "timeout": int(counters_el.get("timeout", 0)),
            "aborted": int(counters_el.get("aborted", 0)),
            "inconclusive": int(counters_el.get("inconclusive", 0)),
            "not_executed": int(counters_el.get("notExecuted", 0)),
            "not_runnable": int(counters_el.get("notRunnable", 0)),
        }

    # Overall outcome
    result_summary_el = root.find(".//trx:ResultSummary", NS)
    summary["outcome"] = (
        result_summary_el.get("outcome", "Unknown")
        if result_summary_el is not None
        else "Unknown"
    )

    # --- Timing ---
    times_el = root.find(".//trx:Times", NS)
    if times_el is not None:
        summary["start_time"] = times_el.get("start", "")
        summary["end_time"] = times_el.get("finish", "")

    # --- Build test ID -> test name mapping ---
    test_definitions = {}
    for td in root.findall(".//trx:TestDefinitions/trx:UnitTest", NS):
        test_id = td.get("id", "")
        test_name = td.get("name", "")
        test_class = ""
        tm = td.find("trx:TestMethod", NS)
        if tm is not None:
            test_class = tm.get("className", "")
        test_definitions[test_id] = {
            "name": test_name,
            "class": test_class,
        }

    # --- Individual test results ---
    tests = []
    for result in root.findall(".//trx:Results/trx:UnitTestResult", NS):
        test_id = result.get("testId", "")
        test_def = test_definitions.get(test_id, {})

        test_name = result.get("testName", test_def.get("name", ""))
        outcome = result.get("outcome", "Unknown")
        duration_str = result.get("duration", "00:00:00")
        start_time = result.get("startTime", "")
        end_time = result.get("endTime", "")

        duration_ms = _parse_duration_ms(duration_str)

        error_message = ""
        error_stacktrace = ""
        output_el = result.find("trx:Output", NS)
        if output_el is not None:
            err_el = output_el.find("trx:ErrorInfo", NS)
            if err_el is not None:
                msg_el = err_el.find("trx:Message", NS)
                stk_el = err_el.find("trx:StackTrace", NS)
                if msg_el is not None and msg_el.text:
                    error_message = msg_el.text.strip()
                if stk_el is not None and stk_el.text:
                    error_stacktrace = stk_el.text.strip()

        test_entry = {
            "name": test_name,
            "class": test_def.get("class", ""),
            "outcome": outcome,
            "duration_ms": duration_ms,
            "start_time": start_time,
            "end_time": end_time,
        }
        if error_message:
            test_entry["error_message"] = error_message
        if error_stacktrace:
            test_entry["error_stacktrace"] = error_stacktrace

        tests.append(test_entry)

    return {
        "file": trx_path,
        "summary": summary,
        "tests": tests,
    }


def _parse_duration_ms(duration_str: str) -> int:
    """Parse HH:MM:SS.fffffff to milliseconds."""
    try:
        parts = duration_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_parts = parts[2].split(".")
        seconds = int(sec_parts[0])
        fraction = int(sec_parts[1][:3]) if len(sec_parts) > 1 else 0
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + fraction
    except (IndexError, ValueError):
        return 0


def print_summary(result: dict):
    """Print a human-readable summary."""
    s = result["summary"]
    print(f"Outcome:   {s['outcome']}")
    print(f"Total:     {s['total']}")
    print(f"Passed:    {s['passed']}")
    print(f"Failed:    {s['failed']}")
    if s.get("error", 0) > 0:
        print(f"Error:     {s['error']}")
    if s.get("start_time"):
        print(f"Started:   {s['start_time']}")
        print(f"Finished:  {s['end_time']}")
    print()

    failures = [t for t in result["tests"] if t["outcome"] != "Passed"]
    if failures:
        print("FAILURES:")
        for t in failures:
            print(f"  [{t['outcome']}] {t['name']} ({t['duration_ms']}ms)")
            if t.get("error_message"):
                first_line = t["error_message"].split("\n")[0]
                print(f"           {first_line}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    trx_path = sys.argv[1]
    fmt = "summary"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]

    if not os.path.exists(trx_path):
        print(f"ERROR: File not found: {trx_path}", file=sys.stderr)
        sys.exit(1)

    result = parse_trx_file(trx_path)

    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print_summary(result)
