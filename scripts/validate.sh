#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
require "$TF"
require helm
require python3
"$TF" -chdir="$ROOT/infra" fmt -check
"$TF" -chdir="$ROOT/infra" init -backend=false -input=false
"$TF" -chdir="$ROOT/infra" validate
for script in "$ROOT"/scripts/*.sh; do bash -n "$script"; done
mkdir -p "$ROOT/.local/validation"
python3 "$ROOT/scripts/check-charts.py"
helm template starrocks-fmea "$ROOT/deploy/charts/starrocks-$CHART_VERSION.tgz" --version "$CHART_VERSION" \
  --namespace starrocks --values "$ROOT/deploy/cluster-values.yaml" \
  > "$ROOT/.local/validation/cluster.yaml"
helm template starrocks-operator "$ROOT/deploy/charts/operator-$CHART_VERSION.tgz" --version "$CHART_VERSION" \
  --namespace starrocks-operator --values "$ROOT/deploy/operator-values.yaml" --include-crds \
  > "$ROOT/.local/validation/operator.yaml"
python3 "$ROOT/scripts/check-render.py"
python3 -m unittest discover -s "$ROOT/experiments" -p 'test_*.py'
