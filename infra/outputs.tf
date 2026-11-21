output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "cluster_name" {
  value = google_container_cluster.lab.name
}

output "zones" {
  value = var.zones
}

output "get_credentials" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.lab.name} --region ${var.region} --project ${var.project_id}"
}
