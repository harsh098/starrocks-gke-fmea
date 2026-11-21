#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
lab_context
# Set SR_FE_POD to query a particular FE during a partition.
POD="${SR_FE_POD:-$CLUSTER-fe-0}"
# MYSQL_PWD is already injected from the Secret inside this container.
kubectl -n "$NAMESPACE" exec -i "$POD" -c fe -- \
  mysql --connect-timeout=10 --host=127.0.0.1 --port=9030 --user=root "$@"
