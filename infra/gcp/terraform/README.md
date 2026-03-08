# Rare Core API on GCP

This Terraform stack provisions the external beta footprint for `rare-identity-core`:

- Artifact Registry
- Cloud SQL for PostgreSQL with private IP
- Memorystore for Redis
- Secret Manager secrets used by Cloud Run
- Cloud KMS keys for identity signing and hosted-key encryption
- Cloud Run v2 service with Direct VPC egress
- External HTTPS Load Balancer with a serverless NEG

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Replace all placeholder values.
3. Run:

```bash
terraform init
terraform plan
terraform apply
```

## Notes

- The stack assumes the VPC network and subnetwork already exist.
- The Cloud Run image must exist in Artifact Registry before the first successful deploy.
- `api_domain` must point at the output `load_balancer_ip`.
- `sendgrid_api_key` may be left `null` for an initial rollout. In that case Cloud Run starts with `RARE_EMAIL_PROVIDER=noop` until you add the SendGrid secret and redeploy.
