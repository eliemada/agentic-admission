#!/usr/bin/env bash
# Download the typst CLI binary for the Vercel build environment (Linux x86_64).
# The binary is placed in api/_bin/ so it gets bundled with the serverless function.

set -euo pipefail

VERSION="v0.13.0"
ARCH="x86_64-unknown-linux-musl"
URL="https://github.com/typst/typst/releases/download/${VERSION}/typst-${ARCH}.tar.xz"

mkdir -p api/_bin

echo "Downloading typst ${VERSION} for ${ARCH}..."
curl -fsSL "$URL" | tar xJ --strip-components=1 -C api/_bin

chmod +x api/_bin/typst
echo "typst installed at api/_bin/typst"
api/_bin/typst --version
