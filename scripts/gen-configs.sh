#!/bin/bash
# Generate config files from templates, substituting env vars from .env
# Run this before `docker compose up` if you've changed .env

set -euo pipefail
cd "$(dirname "$0")/.."

# Load .env
set -a
source .env
set +a

# Generate soularr config
envsubst < soularr/config.ini.template > soularr/config.ini
echo "✅ soularr/config.ini"

# Generate slskd config
envsubst < slskd/config/slskd.yml.template > slskd/config/slskd.yml
echo "✅ slskd/config/slskd.yml"

echo "Done. Generated configs are gitignored."
