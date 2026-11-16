#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source upstream.env
if [ ! -d sysreptor-src/.git ]; then
  git clone --filter=blob:none --no-checkout https://github.com/Syslifters/sysreptor.git sysreptor-src
fi
if [ -n "$(git -C sysreptor-src status --porcelain)" ]; then
  echo 'sysreptor-src has local changes; refusing to overwrite.' >&2
  exit 1
fi
git -C sysreptor-src fetch --depth 1 origin "$SYSREPTOR_COMMIT"
git -C sysreptor-src checkout --detach "$SYSREPTOR_COMMIT"
