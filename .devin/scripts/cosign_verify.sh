#!/usr/bin/env bash
# cosign_verify.sh — Verify release signatures với cosign (Task 3.7).
#
# Keyless signing qua GitHub OIDC:
#   cosign sign-blob --bundle sbom/python.sbom.bundle sbom/python.sbom.json
# Verify (CI, trước deploy):
#   ./cosign_verify.sh sbom/python.sbom.json --bundle sbom/python.sbom.bundle
#
# Nếu cosign chưa cài: FAIL với hướng dẫn (fail-closed — không deploy artifact
# chưa xác minh chữ ký). Chỉ bỏ qua khi --allow-missing được truyền rõ ràng.
set -euo pipefail

ALLOW_MISSING=0
BUNDLE=""
ARTIFACT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    --allow-missing) ALLOW_MISSING=1; shift ;;
    *) ARTIFACT="$1"; shift ;;
  esac
done

if [[ -z "$ARTIFACT" ]]; then
  echo "Usage: $0 <artifact> [--bundle <bundle.json>] [--allow-missing]" >&2
  exit 2
fi

if ! command -v cosign >/dev/null 2>&1; then
  if [[ "$ALLOW_MISSING" == "1" ]]; then
    echo "WARNING: cosign not installed, skipping (--allow-missing)"
    exit 0
  fi
  echo "FAIL: cosign not installed — install via 'go install github.com/sigstore/cosign/v2/cmd/cosign@latest'" >&2
  echo "      hoặc chạy với --allow-missing chỉ khi artifact không cần ký." >&2
  exit 1
fi

if [[ -n "$BUNDLE" ]]; then
  cosign verify-blob --bundle "$BUNDLE" "$ARTIFACT"
else
  # Keyless qua GitHub OIDC (CI): verify trực tiếp theo repo owner
  cosign verify-blob \
    --certificate-identity-regexp "https://github.com/${GITHUB_REPOSITORY_OWNER:-*}/.github/workflows/.*" \
    --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
    "$ARTIFACT"
fi

echo "Signature verification PASSED: $ARTIFACT"