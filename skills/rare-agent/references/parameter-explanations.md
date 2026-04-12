# Parameter Explanations

Use these explanations when the agent needs to explain Rare inputs in plain language.

## name

The display name shown to people. It is not the real identity key. The real identity key is `agent_id`.

## host_mode

Choose who controls signing:

- `hosted-signer`: Rare keeps the signing workflow behind the API. This is the easiest and safest default for most users.
- `self-hosted`: the user keeps the private key locally. This gives more control, but the user is responsible for storage, backup, and recovery. In the supported public workflow, this mode should be operated through `rare-signer` plus the `rare` CLI.

## agent_id

The permanent Rare identity key. It is the Ed25519 public key for the agent.

## hosted_management_token

A sensitive management token used only in `hosted-signer` mode. It authorizes Rare signer operations. Never print it in full, never paste it into chat logs, and never treat it as a public identifier.

## aud

The platform audience string. It identifies which platform a login or full attestation is meant for. The user usually gets this value from the platform itself and it must match exactly.

## platform_url

The base URL of the platform the agent wants to log into or send actions to.

## level

The Rare trust level:

- `L0`: registered key only
- `L1`: email-verified owner connection
- `L2`: stronger social proof connection

## request_id

The tracking id for one upgrade request. Use it to check status, resend an L1 link, or start an L2 social flow.
