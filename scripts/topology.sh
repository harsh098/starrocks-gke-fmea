#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
lab_context
kubectl -n "$NAMESPACE" get pods -l "$SELECTOR" -o wide
kubectl get nodes -L topology.kubernetes.io/zone
"$ROOT/scripts/sql.sh" -e "SHOW FRONTENDS; SHOW BACKENDS;"
