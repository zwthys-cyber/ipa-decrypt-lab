"""Run the repository's test files and attach each file path to its JUnit results."""
import argparse
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET


def run_atom(runner, atom, report_path):
    if runner == "unittest":
        command = [
            sys.executable, "-m", "xmlrunner", "--output-file", str(report_path),
            "discover", "-s", str(atom.parent), "-p", atom.name, "-v",
        ]
        return subprocess.run(command, check=False).returncode

    with report_path.open("wb") as report:
        return subprocess.run(
            ["node", "--test", "--test-reporter=junit", str(atom)],
            stdout=report, check=False,
        ).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runner", choices=("unittest", "node"))
    parser.add_argument("output", type=Path)
    parser.add_argument("atoms", nargs="+", type=Path)
    args = parser.parse_args()

    suites = ET.Element("testsuites")
    failed = False
    with TemporaryDirectory() as directory:
        for atom in args.atoms:
            report = Path(directory) / "atom.xml"
            print(f"Running {atom.as_posix()}", flush=True)
            status = run_atom(args.runner, atom, report)
            try:
                result = ET.parse(report).getroot()
                cases = list(result.iter("testcase"))
                if not cases:
                    raise ValueError("no test cases")
                suite = ET.SubElement(suites, "testsuite", {
                    "name": atom.as_posix(),
                    "tests": str(len(cases)),
                    "failures": str(sum(case.find("failure") is not None for case in cases)),
                    "errors": str(sum(case.find("error") is not None for case in cases)),
                    "skipped": str(sum(case.find("skipped") is not None for case in cases)),
                })
                stderr = []
                for case in cases:
                    case.set("file", atom.as_posix())
                    for output in case.findall("system-err"):
                        case.remove(output)
                        if output.text:
                            stderr.append(f"{case.get('name')}: {output.text}")
                    suite.append(case)
                if stderr:
                    ET.SubElement(suite, "system-err").text = "\n".join(stderr)
            except (OSError, ET.ParseError, ValueError) as error:
                print(f"{atom}: invalid JUnit output: {error}", file=sys.stderr)
                failed = True
            failed |= status != 0
            report.unlink(missing_ok=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suites).write(args.output, encoding="utf-8", xml_declaration=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
