#!/bin/sh
# Explicitly destructive: only this Compose project's named volumes are removed.
set -eu
cd "$(dirname "$0")/.."
docker compose down --volumes --remove-orphans
docker compose run --rm --no-deps provision
docker compose up -d --wait
