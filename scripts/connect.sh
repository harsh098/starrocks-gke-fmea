#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
require gcloud
require "$TF"
mkdir -p "$ROOT/.local"
gcloud container clusters get-credentials \
  "$("$TF" -chdir="$ROOT/infra" output -raw cluster_name)" \
  --region "$("$TF" -chdir="$ROOT/infra" output -raw region)" \
  --project "$("$TF" -chdir="$ROOT/infra" output -raw project_id)"
chmod 600 "$KUBECONFIG"
echo "Kubeconfig: $KUBECONFIG"
