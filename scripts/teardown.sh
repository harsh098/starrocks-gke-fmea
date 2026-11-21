#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
lab_context
require helm
# Only the two lab namespaces and resources in this Terraform state are removed.
# The namespace deletion also removes retained lab PVCs before GKE is destroyed.
python3 "$ROOT/scripts/partition.py" stop
volumes=$(kubectl get pv -o json | python3 -c '
import json,sys
for volume in json.load(sys.stdin)["items"]:
    if volume["spec"].get("claimRef", {}).get("namespace") == "starrocks":
        if volume["spec"].get("persistentVolumeReclaimPolicy") != "Delete":
            sys.exit("A lab PV has a non-Delete reclaim policy. Review disk cleanup before teardown.")
        print(volume["metadata"]["name"])
')
if helm status "$CLUSTER" -n "$NAMESPACE" >/dev/null 2>&1; then
  helm uninstall "$CLUSTER" -n "$NAMESPACE" --wait --timeout 10m
fi
if kubectl -n "$NAMESPACE" get starrockscluster/"$CLUSTER" >/dev/null 2>&1; then
  kubectl -n "$NAMESPACE" wait --for=delete starrockscluster/"$CLUSTER" --timeout=300s
fi
kubectl delete namespace "$NAMESPACE" --wait=true --timeout=10m
for volume in $volumes; do
  if kubectl get "pv/$volume" >/dev/null 2>&1; then
    kubectl wait --for=delete "pv/$volume" --timeout=10m
  fi
done
if helm status starrocks-operator -n starrocks-operator >/dev/null 2>&1; then
  helm uninstall starrocks-operator -n starrocks-operator --wait
fi
kubectl delete namespace starrocks-operator --ignore-not-found
"$TF" -chdir="$ROOT/infra" destroy "$@"
