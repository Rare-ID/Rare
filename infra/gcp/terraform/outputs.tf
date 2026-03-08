output "artifact_registry_repository" {
  value = google_artifact_registry_repository.containers.repository_id
}

output "cloud_run_service" {
  value = google_cloud_run_v2_service.api.name
}

output "load_balancer_ip" {
  value = google_compute_global_address.api.address
}

output "postgres_private_ip" {
  value = google_sql_database_instance.postgres.private_ip_address
}

output "redis_host" {
  value = google_redis_instance.main.host
}
