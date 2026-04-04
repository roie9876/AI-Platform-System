#!/bin/bash
set -euo pipefail

echo "=== Post-deploy: Running smoke tests ==="

# Load azd environment variables
eval "$(azd env get-values | sed 's/^/export /')"

# Run smoke tests
./k8s/scripts/smoke-test.sh aiplatform

echo "Post-deploy complete."
