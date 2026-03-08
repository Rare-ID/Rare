variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "service_name" {
  type    = string
  default = "rare-core-api"
}

variable "api_domain" {
  type = string
}

variable "image" {
  type = string
}

variable "vpc_network" {
  type = string
}

variable "vpc_subnetwork" {
  type = string
}

variable "db_tier" {
  type    = string
  default = "db-custom-2-7680"
}

variable "db_availability_type" {
  type    = string
  default = "REGIONAL"
}

variable "db_disk_size_gb" {
  type    = number
  default = 50
}

variable "redis_memory_size_gb" {
  type    = number
  default = 1
}

variable "min_instances" {
  type    = number
  default = 1
}

variable "max_instances" {
  type    = number
  default = 10
}

variable "container_cpu" {
  type    = string
  default = "1"
}

variable "container_memory" {
  type    = string
  default = "1Gi"
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "sendgrid_api_key" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "sendgrid_from_email" {
  type = string
}

variable "github_client_id" {
  type      = string
  sensitive = true
}

variable "github_client_secret" {
  type      = string
  sensitive = true
}

variable "admin_token" {
  type      = string
  sensitive = true
}
