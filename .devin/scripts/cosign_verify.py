#!/usr/bin/env python3
"""cosign_verify.py — Verify release signatures with cosign (Task 3.7).

Cross-platform port of cosign_verify.sh. Fails closed if cosign is not installed.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify release signatures with cosign")
    parser.add_argument("artifact", help="Artifact path to verify")
    parser.add_argument("--bundle", default="", help="Signature bundle file")
    parser.add_argument("--allow-missing", action="store_true", help="Skip when cosign not installed")
    args = parser.parse_args()

    if shutil.which("cosign") is None:
        if args.allow_missing:
            print("WARNING: cosign not installed, skipping (--allow-missing)")
            return 0
        print(
            "FAIL: cosign not installed -- install via "
            "'go install github.com/sigstore/cosign/v2/cmd/cosign@latest'"
        )
        print("      hoặc chạy với --allow-missing chỉ khi artifact không cần ký.")
        return 1

    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if owner:
        owner = re.escape(owner)
    else:
        owner = ".*"
    cmd: list[str]
    if args.bundle:
        cmd = ["cosign", "verify-blob", "--bundle", args.bundle, args.artifact]
    else:
        cmd = [
            "cosign",
            "verify-blob",
            "--certificate-identity-regexp",
            f"https://github.com/{owner}/.github/workflows/.*",
            "--certificate-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            args.artifact,
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FAIL: cosign verification failed", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    print(f"Signature verification PASSED: {args.artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
