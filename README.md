# StarRocks FMEA on GKE

A small lab for the StarRocks on Kubernetes FMEA article series. [Read Part 1 on the Data on Kubernetes Community blog](https://dok.community/blog/starrocks-kubernetes-fmea-part-1/).

This repository creates the environment for Part 2 and provides procedures to collect your own results. It does not claim that these experiments passed in your cluster.

## What it deploys

| Component | Configuration |
| --- | --- |
| GKE | Regional Standard cluster, Dataplane V2, current Regular-channel version |
| Workers | Three `n2-standard-8` workers, one per zone in `us-west4` |
| Operator and Helm charts | `1.11.1`, matching the version described in Part 1 |
| StarRocks | Shared-nothing, FE and BE images pinned to `3.5.0` |
| FEs | Three voting members, each with 2 CPU and 4 GiB RAM |
| BEs | Three members, each with 4 CPU and 16 GiB RAM |
| Persistent storage | One 100 GiB `premium-rwo` zonal SSD per FE and BE, 600 GiB total |
| Placement | Per-component hostname spread; the three-worker layout places one FE and one BE in each zone |
| Test table | Three replicas per tablet, `MAJORITY` write quorum |
| Access | ClusterIP services; SQL runs through `kubectl exec` |

FE metadata consensus counts voting FEs. BE write quorum counts acknowledgments from replicas of **each tablet**. Both thresholds are two of three here, but they serve different purposes.

The deployment values adapt the sandbox reference. This standalone lab removes external secret controllers, workload-specific cloud permissions, TLS infrastructure, fixed service IPs, telemetry sidecars, backups, and unrelated environments. It uses a smaller FE heap that fits the container memory limit. The current reference uses chart `1.11.4` and a moving `3.5-latest` image; this lab pins explicit versions to make new runs easier to compare. The historical experiment's exact image digest was not recorded, so this is a reproducible baseline rather than an exact historical image reconstruction.

The two upstream chart archives are included under `deploy/charts` with checksums and their license. Setup and validation use those archives so chart downloads cannot silently change between runs.

## Requirements

- An existing GCP project with billing enabled and quota for at least three 8-vCPU workers. Provisioning and upgrades need temporary extra capacity.
- Permission to enable APIs, create a VPC, GKE cluster, node service account, and its project IAM binding.
- OpenTofu 1.8+ or Terraform 1.8+, Google Cloud CLI, `gke-gcloud-auth-plugin`, Helm 3, kubectl compatible with your GKE version, Bash, and Python 3.9+.

The lab incurs charges for GKE, workers, disks, public worker IPs, logging, and network traffic. Worker IPs provide outbound image access. The Kubernetes API is restricted to your configured IPv4 CIDR. No database LoadBalancer is created. Use a separate project and run teardown after the experiments.

## 1. Create GKE

```bash
git clone https://github.com/harsh098/starrocks-gke-fmea.git
cd starrocks-gke-fmea
gcloud auth login
gcloud auth application-default login
gcloud components install gke-gcloud-auth-plugin
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Edit `infra/terraform.tfvars`. Set `project_id` and replace `admin_cidr` with your current public IPv4 address followed by `/32`. The example address is reserved for documentation. If you change regions, also change all three zones.

```bash
tofu -chdir=infra init
tofu -chdir=infra plan -out=lab.tfplan
tofu -chdir=infra apply lab.tfplan
./scripts/connect.sh
```

Use `terraform` in place of `tofu` if preferred. Scripts select `tofu` when available; set `TF_BIN=terraform` to use Terraform explicitly. Use one CLI consistently for a given state. State and local values are ignored by Git. The lab enables project APIs and leaves them enabled on teardown.

Credentials use `.local/kubeconfig` by default, keeping the lab separate from your normal kubectl context. Every mutation script checks that its context matches this repository's Terraform outputs. To run kubectl commands directly in a shell, set:

```bash
export KUBECONFIG="$PWD/.local/kubeconfig"
```

## 2. Deploy StarRocks

```bash
./scripts/deploy.sh
./scripts/smoke-test.sh
./scripts/topology.sh
```

The first deployment generates a random root password in `.local/root-password` and creates the `starrocks-admin-password` Kubernetes Secret. Later runs reuse the existing Secret. The Helm initialization job sets the database password. FE and BE containers explicitly receive `MYSQL_PWD` from that Secret. Updating the Secret later does not change the database password or the environment of existing containers.

The smoke check verifies worker placement, ready pods, database membership, and reads from a table with three replicas. It creates `fmea.events` only if the table is absent. If a step fails, inspect the pod events, init-password job, and FE/BE logs before running a disruption.

If you have less than 600 GiB of free SSD quota, use the optional profile below **on the first deployment**. It creates six 50 GiB volumes, totaling 300 GiB, and differs from the article's storage capacity. Use the same override on subsequent deploys. Do not switch an existing 100 GiB cluster to smaller volumes; PVCs cannot be shrunk.

```bash
SR_VALUES_FILE=deploy/small-storage-values.yaml ./scripts/deploy.sh
```

```bash
./scripts/sql.sh -e "SHOW FRONTENDS; SHOW BACKENDS;"
./scripts/sql.sh -e "SELECT * FROM fmea.events ORDER BY event_id;"
```

## 3. Run the experiments

Follow [the experiment guide](experiments/README.md). It covers FE/BE restarts, planned worker drain, worker replacement, a zone network partition, and stale credentials after a password change. Each procedure states the fault, observations, and recovery steps. Record results using [the run template](docs/run-record.md).

Run one disruption at a time. Wait for all voting FEs, BEs, and tablet replicas to recover before moving to the next experiment. A Ready pod alone does not prove database membership or data recovery. These checks do not establish full ACID compliance or linearizability.

## 4. Remove the lab

```bash
./scripts/teardown.sh
```

The script removes the partition, StarRocks, and retained PVCs while the operator and GKE are still available, then runs `tofu destroy` for the resources in this state. Accept the destroy plan to finish. Deleting PVCs destroys the lab data. Check the GCP console for leftover disks if a volume was already detached or its reclaim policy was changed. Keep `infra/terraform.tfstate` until cleanup is complete.

If Kubernetes is already unavailable, run `tofu -chdir=infra destroy` and check for retained disks separately. If your public IP changes, update `admin_cidr` and apply the infrastructure again before reconnecting.

## Validation and references

For static checks, install the packages in `requirements-dev.txt` in a Python virtual environment, then run `./scripts/validate.sh`. Cloud validation status and limitations are recorded in [validation](docs/validation.md).

- [StarRocks Operator v1.11.1](https://github.com/StarRocks/starrocks-kubernetes-operator/tree/v1.11.1)
- [Password rotation guide](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.1/doc/change_root_password_howto.md)
- [GKE Dataplane V2](https://cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2)
- [GKE node configuration](https://cloud.google.com/kubernetes-engine/docs/how-to/node-system-config)
- [Google Terraform provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_cluster)
- [Kubernetes NetworkPolicy semantics](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
