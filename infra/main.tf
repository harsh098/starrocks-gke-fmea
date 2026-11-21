locals {
  services = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])
  labels = { purpose = "starrocks-fmea" }
}

resource "google_project_service" "lab" {
  for_each           = local.services
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "lab" {
  name                    = var.cluster_name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.lab]
}

resource "google_compute_subnetwork" "lab" {
  name                     = var.cluster_name
  network                  = google_compute_network.lab.id
  region                   = var.region
  ip_cidr_range            = "10.60.0.0/20"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.64.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.65.0.0/20"
  }
}

resource "google_service_account" "nodes" {
  account_id   = "${var.cluster_name}-nodes"
  display_name = "StarRocks FMEA GKE nodes"
  depends_on   = [google_project_service.lab]
}

resource "google_project_iam_member" "nodes" {
  project = var.project_id
  role    = "roles/container.defaultNodeServiceAccount"
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_container_cluster" "lab" {
  name                     = var.cluster_name
  location                 = var.region
  node_locations           = var.zones
  network                  = google_compute_network.lab.id
  subnetwork               = google_compute_subnetwork.lab.id
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false
  networking_mode          = "VPC_NATIVE"
  datapath_provider        = "ADVANCED_DATAPATH"
  resource_labels          = local.labels

  release_channel {
    channel = "REGULAR"
  }
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.admin_cidr
      display_name = "lab-operator"
    }
  }
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
  addons_config {
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
  }
  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  lifecycle {
    precondition {
      condition     = alltrue([for zone in var.zones : startswith(zone, "${var.region}-")])
      error_message = "All three zones must be in region."
    }
  }
  depends_on = [google_project_service.lab]
}

resource "google_container_node_pool" "experiment" {
  name           = "experiments"
  location       = var.region
  cluster        = google_container_cluster.lab.name
  node_locations = var.zones
  # For a regional pool this is PER ZONE, giving three workers in total.
  node_count = 1

  management {
    auto_repair  = true
    auto_upgrade = true
  }
  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }
  node_config {
    machine_type    = var.machine_type
    disk_type       = "pd-balanced"
    disk_size_gb    = 50
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = merge(local.labels, { "starrocks-lab" = "true" })
    metadata        = { "disable-legacy-endpoints" = "true" }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    linux_node_config {
      sysctls = {
        "vm.max_map_count" = "262144"
        "vm.swappiness"    = "0"
      }
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
  depends_on = [google_project_iam_member.nodes]
}
