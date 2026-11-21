#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.local/kubeconfig}"
NAMESPACE=starrocks
CLUSTER=starrocks-fmea
SELECTOR="app.starrocks.ownerreference/name=$CLUSTER"
CHART_VERSION=1.11.1

if [[ -n "${TF_BIN:-}" ]]; then
  TF="$TF_BIN"
elif command -v tofu >/dev/null; then
  TF=tofu
else
  TF=terraform
fi

require() {
  command -v "$1" >/dev/null || { echo "Missing command: $1" >&2; exit 1; }
}

lab_context() {
  require kubectl
  require "$TF"
  local project region name expected
  project=$("$TF" -chdir="$ROOT/infra" output -raw project_id)
  region=$("$TF" -chdir="$ROOT/infra" output -raw region)
  name=$("$TF" -chdir="$ROOT/infra" output -raw cluster_name)
  expected="gke_${project}_${region}_${name}"
  if [[ "$(kubectl config current-context)" != "$expected" ]]; then
    echo "Connect to the lab first with ./scripts/connect.sh. Expected context: $expected" >&2
    exit 1
  fi
}
