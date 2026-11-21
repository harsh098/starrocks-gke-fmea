#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
lab_context
require helm
require python3
python3 "$ROOT/scripts/check-charts.py"
mkdir -p "$ROOT/.local"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Generate a password only on the first deployment. Never replace it on reruns.
# It stays out of Terraform state, Helm values, command arguments, and the repo.
if ! kubectl -n "$NAMESPACE" get secret starrocks-admin-password >/dev/null 2>&1; then
  umask 077
  python3 -c 'import secrets; print(secrets.token_hex(24), end="")' > "$ROOT/.local/root-password"
  kubectl -n "$NAMESPACE" create secret generic starrocks-admin-password \
    --from-file=password="$ROOT/.local/root-password"
fi

extra_values=()
if [[ -n "${SR_VALUES_FILE:-}" ]]; then
  [[ -f "$SR_VALUES_FILE" ]] || { echo "Values file not found: $SR_VALUES_FILE" >&2; exit 1; }
  extra_values=(--values "$SR_VALUES_FILE")
fi
helm upgrade --install starrocks-operator "$ROOT/deploy/charts/operator-$CHART_VERSION.tgz" \
  --namespace starrocks-operator --create-namespace --version "$CHART_VERSION" \
  --values "$ROOT/deploy/operator-values.yaml" --wait --timeout 5m
kubectl wait --for=condition=Established crd/starrocksclusters.starrocks.com --timeout=120s
helm upgrade --install "$CLUSTER" "$ROOT/deploy/charts/starrocks-$CHART_VERSION.tgz" \
  --namespace "$NAMESPACE" --version "$CHART_VERSION" \
  --values "$ROOT/deploy/cluster-values.yaml" "${extra_values[@]}" --wait --wait-for-jobs --timeout 20m
kubectl -n "$NAMESPACE" rollout status statefulset/"$CLUSTER-fe" --timeout=15m
kubectl -n "$NAMESPACE" rollout status statefulset/"$CLUSTER-be" --timeout=15m
"$ROOT/scripts/sql.sh" -e "SHOW FRONTENDS; SHOW BACKENDS;"
echo "Deployment complete. Run ./scripts/smoke-test.sh next."
