"""Installed-wheel function CLI acceptance; launch with python -I after wheel install."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import patchreplay
from patchreplay.function.workflow import load_registered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    origin = Path(patchreplay.__file__).resolve()
    checkout = Path(__file__).resolve().parents[1]
    if origin.is_relative_to(checkout / "src"):
        raise RuntimeError("Wheel smoke must import the installed wheel, not the source checkout")
    args.output.mkdir(parents=True, exist_ok=False)
    def cli(*argv, expected=0):
        result = subprocess.run([sys.executable, "-I", "-m", "patchreplay", *map(str, argv)],
                                capture_output=True, text=True, timeout=300, cwd=args.output)
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout
    names = cli("function-list").splitlines()
    for name in names:
        load_registered(name)
    record = {"module_origin": str(origin), "registered_cases": names, "live": bool(args.image)}
    if args.image:
        first = json.loads(cli("function-run", "good", "--image", args.image, "--output", args.output / "runs"))
        cli("verify", first["package"])
        second = json.loads(cli("replay", first["package"], "--output", args.output / "replays"))
        assert first["package"] != second["package"]
        cli("verify", second["package"])
        record.update(first=first, replay=second)
    else:
        # Invalid image is rejected before any Docker invocation.
        cli("function-run", "good", "--image", "latest", "--output", args.output / "rejected", expected=2)
    (args.output / "wheel.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
