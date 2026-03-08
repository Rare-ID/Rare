locals {
  prefix                  = "${var.service_name}-${var.environment}"
  api_domain              = trimspace(var.api_domain)
  public_base_url         = "https://${local.api_domain}"
  sendgrid_enabled        = var.sendgrid_api_key != null && trimspace(var.sendgrid_api_key) != ""
  postgres_secret_id      = "${local.prefix}-postgres-dsn"
  redis_secret_id         = "${local.prefix}-redis-url"
  admin_secret_id         = "${local.prefix}-admin-token"
  keyring_secret_id       = "${local.prefix}-keyring"
  sendgrid_key_secret_id  = "${local.prefix}-sendgrid-api-key"
  github_id_secret_id     = "${local.prefix}-github-client-id"
  github_secret_secret_id = "${local.prefix}-github-client-secret"
}

data "google_compute_network" "main" {
  name = var.vpc_network
}

data "google_compute_subnetwork" "main" {
  name   = var.vpc_subnetwork
  region = var.region
}

resource "google_project_service" "services" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudkms.googleapis.com",
    "compute.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
  ])

  project                    = var.project_id
  service                    = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "${local.prefix}-containers"
  description   = "Rare Core API container images for ${var.environment}"
  format        = "DOCKER"

  depends_on = [google_project_service.services]
}

resource "google_compute_global_address" "private_service_access" {
  name          = "${local.prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = data.google_compute_network.main.id

  depends_on = [google_project_service.services]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = data.google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]

  depends_on = [google_project_service.services]
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "google_sql_database_instance" "postgres" {
  name                = "${local.prefix}-pg"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.db_tier
    availability_type = var.db_availability_type
    disk_size          = var.db_disk_size_gb
    disk_type          = "PD_SSD"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = data.google_compute_network.main.id
      enable_private_path_for_google_cloud_services = true
    }
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_sql_database" "app" {
  name     = "rare"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "app" {
  name     = "rare"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

resource "google_redis_instance" "main" {
  name               = "${local.prefix}-redis"
  region             = var.region
  tier               = "STANDARD_HA"
  memory_size_gb     = var.redis_memory_size_gb
  authorized_network = data.google_compute_network.main.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_secret_manager_secret" "postgres_dsn" {
  secret_id = local.postgres_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "postgres_dsn" {
  secret      = google_secret_manager_secret.postgres_dsn.id
  secret_data = "postgresql://rare:${random_password.db_password.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/${google_sql_database.app.name}"
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = local.redis_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_url" {
  secret      = google_secret_manager_secret.redis_url.id
  secret_data = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
}

resource "google_secret_manager_secret" "admin_token" {
  secret_id = local.admin_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "admin_token" {
  secret      = google_secret_manager_secret.admin_token.id
  secret_data = var.admin_token
}

resource "google_secret_manager_secret" "keyring" {
  secret_id = local.keyring_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "sendgrid_api_key" {
  count     = local.sendgrid_enabled ? 1 : 0
  secret_id = local.sendgrid_key_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "sendgrid_api_key" {
  count       = local.sendgrid_enabled ? 1 : 0
  secret      = google_secret_manager_secret.sendgrid_api_key[0].id
  secret_data = var.sendgrid_api_key
}

resource "google_secret_manager_secret" "github_client_id" {
  secret_id = local.github_id_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "github_client_id" {
  secret      = google_secret_manager_secret.github_client_id.id
  secret_data = var.github_client_id
}

resource "google_secret_manager_secret" "github_client_secret" {
  secret_id = local.github_secret_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "github_client_secret" {
  secret      = google_secret_manager_secret.github_client_secret.id
  secret_data = var.github_client_secret
}

resource "google_kms_key_ring" "main" {
  name     = "${local.prefix}-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "identity_signer" {
  name     = "${local.prefix}-identity"
  key_ring = google_kms_key_ring.main.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm = "EC_SIGN_ED25519"
  }
}

resource "google_kms_crypto_key" "rare_signer" {
  name     = "${local.prefix}-rare-signer"
  key_ring = google_kms_key_ring.main.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm = "EC_SIGN_ED25519"
  }
}

resource "google_kms_crypto_key" "hosted_cipher" {
  name     = "${local.prefix}-hosted-key-cipher"
  key_ring = google_kms_key_ring.main.id
  purpose  = "ENCRYPT_DECRYPT"
}

resource "google_service_account" "run" {
  account_id   = substr("${var.service_name}-${var.environment}", 0, 28)
  display_name = "Rare Core API ${var.environment}"
}

resource "google_project_iam_member" "run_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "run_secret_viewer" {
  project = var.project_id
  role    = "roles/secretmanager.viewer"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "run_secret_version_adder" {
  project = var.project_id
  role    = "roles/secretmanager.secretVersionAdder"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "run_kms_signer" {
  project = var.project_id
  role    = "roles/cloudkms.signerVerifier"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "run_kms_encrypter" {
  project = var.project_id
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = var.deletion_protection

  template {
    service_account                  = google_service_account.run.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = data.google_compute_network.main.id
        subnetwork = data.google_compute_subnetwork.main.id
      }
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.container_cpu
          memory = var.container_memory
        }
      }

      startup_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 6
        http_get {
          path = "/readyz"
          port = 8080
        }
      }

      liveness_probe {
        timeout_seconds   = 3
        period_seconds    = 30
        failure_threshold = 3
        http_get {
          path = "/healthz"
          port = 8080
        }
      }

      env {
        name  = "RARE_ENV"
        value = var.environment
      }

      env {
        name  = "RARE_PUBLIC_BASE_URL"
        value = local.public_base_url
      }

      env {
        name  = "RARE_STORAGE_BACKEND"
        value = "postgres_redis"
      }

      env {
        name  = "RARE_STATE_NAMESPACE"
        value = "${var.environment}:default"
      }

      env {
        name  = "RARE_KEY_PROVIDER"
        value = "gcp_secret_manager"
      }

      env {
        name  = "RARE_GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "RARE_GCP_KEYRING_SECRET"
        value = google_secret_manager_secret.keyring.secret_id
      }

      env {
        name  = "RARE_HOSTED_KEY_CIPHER"
        value = "gcp_kms"
      }

      env {
        name  = "RARE_HOSTED_KEY_CIPHER_KMS_KEY"
        value = google_kms_crypto_key.hosted_cipher.id
      }

      env {
        name  = "RARE_KMS_IDENTITY_KEY_VERSION"
        value = "${google_kms_crypto_key.identity_signer.id}/cryptoKeyVersions/1"
      }

      env {
        name  = "RARE_KMS_RARE_SIGNER_KEY_VERSION"
        value = "${google_kms_crypto_key.rare_signer.id}/cryptoKeyVersions/1"
      }

      env {
        name  = "RARE_KMS_IDENTITY_KID"
        value = "${local.prefix}-identity"
      }

      env {
        name  = "RARE_KMS_RARE_SIGNER_KID"
        value = "${local.prefix}-rare-signer"
      }

      env {
        name  = "RARE_EMAIL_PROVIDER"
        value = local.sendgrid_enabled ? "sendgrid" : "noop"
      }

      dynamic "env" {
        for_each = local.sendgrid_enabled ? [var.sendgrid_from_email] : []
        content {
          name  = "RARE_SENDGRID_FROM_EMAIL"
          value = env.value
        }
      }

      env {
        name  = "RARE_SOCIAL_PROVIDER_ALLOWLIST"
        value = "github"
      }

      env {
        name  = "RARE_DNS_RESOLVER"
        value = "public"
      }

      env {
        name  = "RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS"
        value = "false"
      }

      env {
        name = "RARE_POSTGRES_DSN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.postgres_dsn.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "RARE_REDIS_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.redis_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "RARE_ADMIN_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.admin_token.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = local.sendgrid_enabled ? [google_secret_manager_secret.sendgrid_api_key[0].secret_id] : []
        content {
          name = "RARE_SENDGRID_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      env {
        name = "RARE_GITHUB_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_client_id.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "RARE_GITHUB_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_client_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.run_secret_accessor,
    google_project_iam_member.run_secret_viewer,
    google_project_iam_member.run_secret_version_adder,
    google_project_iam_member.run_kms_signer,
    google_project_iam_member.run_kms_encrypter,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "${local.prefix}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_security_policy" "armor" {
  name = "${local.prefix}-armor"

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default allow"
  }
}

resource "google_compute_backend_service" "api" {
  name                  = "${local.prefix}-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.armor.id

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
}

resource "google_compute_managed_ssl_certificate" "api" {
  name = "${local.prefix}-cert"

  managed {
    domains = [local.api_domain]
  }
}

resource "google_compute_url_map" "api" {
  name            = "${local.prefix}-urlmap"
  default_service = google_compute_backend_service.api.id
}

resource "google_compute_target_https_proxy" "api" {
  name             = "${local.prefix}-https-proxy"
  url_map          = google_compute_url_map.api.id
  ssl_certificates = [google_compute_managed_ssl_certificate.api.id]
}

resource "google_compute_global_address" "api" {
  name = "${local.prefix}-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${local.prefix}-https"
  target                = google_compute_target_https_proxy.api.id
  ip_address            = google_compute_global_address.api.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
