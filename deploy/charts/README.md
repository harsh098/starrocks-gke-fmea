# Pinned upstream Helm charts

These unmodified chart packages come from [StarRocks Operator release v1.11.1](https://github.com/StarRocks/starrocks-kubernetes-operator/releases/tag/v1.11.1):

- `operator-1.11.1.tgz`
- `starrocks-1.11.1.tgz`

`SHA256SUMS` records the package hashes. `LICENSE` is the upstream Apache License 2.0 for these charts. The corresponding source is [the versioned Helm chart directory](https://github.com/StarRocks/starrocks-kubernetes-operator/tree/v1.11.1/helm-charts/charts/kube-starrocks/charts).

The lab verifies these files before deployment and validation. To change versions, update both packages, their checksums, `CHART_VERSION` in `scripts/common.sh`, the operator image, and the rendered-manifest checks. Validate the new CRD and record the version change with experiment results.
