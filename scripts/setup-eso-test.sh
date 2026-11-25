#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
cd "$ROOT"
lab_context
require helm
umask 077
mkdir -p .local
helm upgrade --install external-secrets external-secrets \
  --repo https://charts.external-secrets.io --version 2.12.0 \
  --namespace external-secrets --create-namespace --wait --timeout 5m
kubectl create namespace starrocks-eso-source --dry-run=client -o yaml | kubectl apply -f -
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 -d > .local/eso-baseline-password
test -s .local/eso-baseline-password
kubectl -n starrocks-eso-source create secret generic starrocks-admin-password \
  --from-file=password=.local/eso-baseline-password --dry-run=client -o yaml \
  | kubectl apply --server-side --force-conflicts -f -
kubectl apply -f experiments/eso-lab.yaml
kubectl -n starrocks wait --for=condition=Ready \
  secretstore/starrocks-password-source externalsecret/starrocks-admin-password --timeout=120s
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 -d | cmp -s - .local/eso-baseline-password
echo 'ESO ready: hourly refresh, synchronized baseline password.'
