variable "project_id" {
  description = "Existing, billing-enabled GCP project for the lab."
  type        = string
}

variable "cluster_name" {
  description = "Name prefix for lab resources."
  type        = string
  default     = "starrocks-fmea"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,22}[a-z0-9]$", var.cluster_name))
    error_message = "Use 2 to 24 lowercase letters, digits, or hyphens, starting with a letter and ending with a letter or digit."
  }
}

variable "region" {
  description = "GCP region. The default matches the article."
  type        = string
  default     = "us-west4"
}

variable "zones" {
  description = "Exactly three distinct zones in the chosen region. One worker runs in each zone."
  type        = list(string)
  default     = ["us-west4-a", "us-west4-b", "us-west4-c"]

  validation {
    condition     = length(var.zones) == 3 && length(distinct(var.zones)) == 3
    error_message = "Provide exactly three distinct zones."
  }
}

variable "admin_cidr" {
  description = "Public IPv4 CIDR allowed to reach the Kubernetes API, normally your current public IP followed by /32."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && can(regex("/(2[4-9]|3[0-2])$", var.admin_cidr))
    error_message = "Use an IPv4 CIDR with a /24 through /32 prefix."
  }
}

variable "machine_type" {
  description = "Each worker must fit one FE (2 CPU, 4 GiB), one BE (4 CPU, 16 GiB), and system pods."
  type        = string
  default     = "n2-standard-8"
}
