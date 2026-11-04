import argparse
from .host import demo

parser = argparse.ArgumentParser(description="Run registered host-oracle experiments (Docker required)")
parser.add_argument("--image", required=True, help="Immutable local image ID")
parser.add_argument("--output", required=True)
args = parser.parse_args()
report = demo(args.image, args.output)
print(f"Expected outcomes matched: {report['expected_outcomes_matched']}; observations: {len(report['observations'])}")
raise SystemExit(0 if report["expected_outcomes_matched"] else 1)
