# Rare GCP Deployment

This workspace now includes the deployment assets for the Rare Core API external beta:

- `rare-identity-core/Dockerfile`: production image build for Cloud Run
- `infra/gcp/terraform/`: GCP infrastructure for Cloud Run, Cloud SQL, Redis, Secret Manager, KMS, and HTTPS load balancing
- `.github/workflows/deploy-rare-core.yml`: image build and Cloud Run deploy workflow

## Runtime Contract

The Cloud Run service expects these production settings:

- `RARE_ENV=staging|prod`
- `RARE_PUBLIC_BASE_URL=https://api.<domain>`
- `RARE_STORAGE_BACKEND=postgres_redis`
- `RARE_KEY_PROVIDER=gcp_secret_manager`
- `RARE_HOSTED_KEY_CIPHER=gcp_kms`
- `RARE_EMAIL_PROVIDER=sendgrid`
- `RARE_SOCIAL_PROVIDER_ALLOWLIST=github`
- `RARE_DNS_RESOLVER=public`
- `RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS=false`

Use Direct VPC egress with `private-ranges-only`. This service needs private access to Cloud SQL and Redis, but it must keep Google API traffic and third-party outbound traffic on public egress for Secret Manager, KMS, GitHub OAuth, SendGrid, and public DNS lookups.

## App-Level Production Features

- Real SendGrid mail send for L1 upgrade links
- Real GitHub OAuth exchange for L2 upgrade
- Real Secret Manager keyring storage
- Public DNS TXT verification for platform onboarding
- `GET /healthz` and `GET /readyz`

## Before Applying Terraform

1. Build and push the image referenced by `image` in `terraform.tfvars`.
2. Point `api_domain` at the eventual load balancer IP.
3. Fill in `sendgrid_api_key`, `sendgrid_from_email`, `github_client_id`, `github_client_secret`, and `admin_token`.
4. Ensure the target VPC network and subnetwork already exist.
