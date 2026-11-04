"""Offline host-only CLI; never launches Docker, candidate code or a network client."""
import argparse
import json
import os


def password(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError("Signing password environment variable is missing or empty")
    return value.encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Authenticate evidence against an external key and expected subject")
    commands = parser.add_subparsers(dest="command", required=True)
    key = commands.add_parser("keygen")
    key.add_argument("--private-key", required=True)
    key.add_argument("--public-key", required=True)
    key.add_argument("--password-env", required=True)
    prep = commands.add_parser("prepare", help="Draft an expectation to review and store separately")
    prep.add_argument("--subject", required=True)
    prep.add_argument("--kind", choices=["observer-v1", "patchreplay-v1", "host-function-v1"], required=True)
    prep.add_argument("--output", required=True)
    signing = commands.add_parser("sign")
    signing.add_argument("--subject", required=True)
    signing.add_argument("--expectation", required=True)
    signing.add_argument("--private-key", required=True)
    signing.add_argument("--password-env", required=True)
    signing.add_argument("--output", required=True)
    verification = commands.add_parser("verify")
    verification.add_argument("--bundle", required=True)
    verification.add_argument("--trusted-key", required=True)
    verification.add_argument("--expectation", required=True)
    args = parser.parse_args(argv)
    try:
        from . import core
        if args.command == "keygen":
            result = {"key_id": core.keygen(args.private_key, args.public_key, password(args.password_env))}
        elif args.command == "prepare":
            result = core.prepare(args.subject, args.kind, args.output)
        elif args.command == "sign":
            result = core.sign(args.subject, args.expectation, args.private_key, password(args.password_env), args.output)
        else:
            result = core.verify(args.bundle, args.trusted_key, args.expectation)
        print(json.dumps(result, indent=2))
        return 0
    except ImportError:
        print(json.dumps({"status": "UNAVAILABLE", "reason": "Install the provenance optional dependency or requirements-provenance.lock"}))
        return 2
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}))
        return 1
