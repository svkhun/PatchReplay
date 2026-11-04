"""Sign real function evidence with ephemeral host keys; no private key is retained."""
import argparse
from pathlib import Path
import tempfile

from patchreplay.integrity import write_json
from patchreplay_provenance import core


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    public, expected = args.output / "trust/public.pem", args.output / "trust/expected.json"
    bundle = args.output / "bundle"
    with tempfile.TemporaryDirectory(prefix="function-signing-") as temporary:
        import secrets
        password = secrets.token_urlsafe(32).encode()
        private = Path(temporary) / "private.pem"
        core.keygen(private, public, password)
        core.prepare(args.subject, "host-function-v1", expected)
        core.sign(args.subject, expected, private, password, bundle)
        result = core.verify(bundle, public, expected)
    write_json(args.output / "result.json", result)
    print(result["status"])


if __name__ == "__main__":
    main()
