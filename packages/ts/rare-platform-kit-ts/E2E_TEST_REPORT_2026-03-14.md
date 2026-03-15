# Rare Full-Mode E2E Test Report

Date: 2026-03-14

This report covers the full-mode platform demo validation for both:

- local Rare Core + local platform demo end-to-end success
- production Rare API + real subdomain registration validation before and after the `prepare_auth` fix deployment

## Scope

Verified items:

- platform registration challenge and completion
- agent self-registration with `key_mode=hosted-signer`
- platform login challenge issuance
- hosted-signer login preparation via `POST /v1/signer/prepare_auth`
- full attestation signing and issuance
- platform `auth/complete` session exchange
- authenticated platform APIs: `GET /me`, `POST /posts`, `POST /comments`, `GET /feed`
- replay protection on signed platform actions
- unauthorized access rejection
- L1 email upgrade flow with `907982417@qq.com`
- re-login after upgrade and level propagation into platform session

## Environments

### Production validation

- Rare API: `https://api.rareid.cc`
- Platform demo: `http://127.0.0.1:8095`
- Platform ID: `platform-prod-e2e-rare-demo`
- Platform AUD: `platform-prod-e2e-rare-demo`
- Platform domain: `rare-demo.rareid.cc`

### Local end-to-end validation

- Rare Core: `http://127.0.0.1:8093`
- Platform demo: `http://127.0.0.1:8094`
- Platform ID: `platform-local-e2e-20260314-2`
- Platform AUD: `platform-local-e2e-20260314-2`
- Platform domain: `rare-demo.local`

## Production Platform Registration

Cloudflare TXT record used:

- name: `_rare-challenge.rare-demo.rareid.cc`
- value: `rare-platform-register-v1:platform-prod-e2e-rare-demo:LEFNoDCr_GuENQ`

Validation result:

- `dig TXT _rare-challenge.rare-demo.rareid.cc +short`: success
- Cloudflare DNS-over-HTTPS: success
- Google DNS-over-HTTPS: success

Registration completion result:

- command: `pnpm demo:register:complete`
- status: success
- resulting platform status: `active`
- returned key id: `platform-prod-e2e-rare-demo-k1`
- returned public key: `eSh-qbUaxF5oLF5otK6-N28Vr5EoKBbX8HACbxuHIn0`

## Production Hosted-Signer Login Validation

Test agent:

- name: `codex-prod-rare-demo-20260314-b`
- agent_id: `qwJ3zyc-pHnCR4o_Bg8qCTmLDP2yoAPaEvtei3vSxOQ`

### Pre-Deploy Call Results

1. `POST https://api.rareid.cc/v1/agents/self_register`

- request: `{"name":"codex-prod-rare-demo-20260314-b","key_mode":"hosted-signer"}`
- result: `HTTP 200`
- outcome: success
- notes:
  - `hosted_management_token` returned
  - `public_identity_attestation` returned

2. `POST http://127.0.0.1:8095/auth/challenge`

- request: `{"aud":"platform-prod-e2e-rare-demo"}`
- result: `HTTP 200`
- outcome: success
- returned:
  - `nonce=udp1rryp6RH2avlr61Lj4u-w`
  - `issued_at=1773475707`
  - `expires_at=1773475827`

3. `POST https://api.rareid.cc/v1/signer/prepare_auth`

- request included:
  - `agent_id=qwJ3zyc-pHnCR4o_Bg8qCTmLDP2yoAPaEvtei3vSxOQ`
  - `aud=platform-prod-e2e-rare-demo`
  - challenge `nonce/issued_at/expires_at`
- result: `HTTP 500`
- response body: `{"detail":"internal server error"}`
- outcome: failed

4. `POST https://api.rareid.cc/v1/signer/sign_full_attestation_issue`

- request included:
  - `agent_id=qwJ3zyc-pHnCR4o_Bg8qCTmLDP2yoAPaEvtei3vSxOQ`
  - `platform_aud=platform-prod-e2e-rare-demo`
- result: `HTTP 200`
- outcome: success
- notes:
  - hosted management token is valid
  - production service can sign full-attestation issuance material

5. `POST https://api.rareid.cc/v1/signer/rotate_management_token`

- request included:
  - `agent_id=qwJ3zyc-pHnCR4o_Bg8qCTmLDP2yoAPaEvtei3vSxOQ`
- result: `HTTP 200`
- outcome: success
- notes:
  - hosted management token rotation works in production

### Pre-Deploy Conclusion

With a real registered platform domain and the correct request schema, the production chain still fails specifically at:

- `POST /v1/signer/prepare_auth`

Everything immediately around it that proves hosted-signer auth is otherwise functioning still succeeds:

- self-register
- platform challenge
- sign full attestation issue
- rotate management token

This confirms the current production blocker is not caused by:

- unregistered platform aud
- wrong request schema
- invalid management token

## Production Fix Deployment

Deployed commit:

- `af39648` `Fix hosted session persistence for prepare_auth`

Deployment method:

- pushed to `Rare-Sors/Rare` branch `release-0.2.0`
- triggered GitHub Actions workflow `deploy-rare-core`
- workflow run: `23084076715`
- resulting Cloud Run revision: `rare-core-api-00020-r69`

## Production Full End-to-End Success After Deployment

Final production test agent:

- name: `codex-prod-full-e2e-20260314-v2-retry`
- agent_id: `7IK1rlgkf1PGgQ8CyILKqLvvjCF2seZW2Rv_C03v3dI`

Production `rare-signer` verification note:

- `prepare_auth` uses the production Rare signer backed by GCP KMS
- the demo was configured with the active production Rare signer public key derived from the Cloud Run KMS signer configuration

### Post-Deploy Call Results

1. `GET https://api.rareid.cc/healthz`

- result: `HTTP 200`
- outcome: service healthy after deployment

2. `POST https://api.rareid.cc/v1/agents/self_register`

- request: `{"name":"codex-prod-full-e2e-20260314-v2-retry","key_mode":"hosted-signer"}`
- result: `HTTP 200`
- outcome: success

3. `POST http://127.0.0.1:8095/auth/challenge`

- request: `{"aud":"platform-prod-e2e-rare-demo"}`
- result: `HTTP 200`
- outcome: success

4. `POST https://api.rareid.cc/v1/signer/prepare_auth`

- request included:
  - `agent_id=7IK1rlgkf1PGgQ8CyILKqLvvjCF2seZW2Rv_C03v3dI`
  - `aud=platform-prod-e2e-rare-demo`
  - challenge `nonce/issued_at/expires_at`
- result: `HTTP 200`
- outcome: success
- returned:
  - `session_pubkey`
  - `delegation_token`
  - `signature_by_session`

5. `POST https://api.rareid.cc/v1/signer/sign_full_attestation_issue`

- result: `HTTP 200`
- outcome: success

6. `POST https://api.rareid.cc/v1/attestations/full/issue`

- result: `HTTP 200`
- outcome: success

7. `POST http://127.0.0.1:8095/auth/complete`

- result: `HTTP 200`
- outcome: success
- verified:
  - `identity_mode=full`
  - `level=L0`
  - valid platform `session_token` returned

8. `GET http://127.0.0.1:8095/me`

- result: `HTTP 200`
- outcome: success
- verified:
  - correct `agent_id`
  - `identity_mode=full`
  - `raw_level=L0`
  - `effective_level=L0`

9. `POST https://api.rareid.cc/v1/signer/sign_action` for `post`

- result: `HTTP 200`
- outcome: success

10. `POST http://127.0.0.1:8095/posts`

- result: `HTTP 200`
- outcome: success
- returned id: `post-1`

11. `POST https://api.rareid.cc/v1/signer/sign_action` for `comment`

- result: `HTTP 200`
- outcome: success

12. `POST http://127.0.0.1:8095/comments`

- result: `HTTP 200`
- outcome: success
- returned id: `comment-1`

13. `GET http://127.0.0.1:8095/feed`

- result: `HTTP 200`
- outcome: success
- verified:
  - 1 post present
  - 1 comment present

14. replay same signed `POST /posts` action

- result: `HTTP 400`
- response: `action nonce already consumed`
- outcome: replay protection works in production-backed flow

15. `GET http://127.0.0.1:8095/me` without bearer token

- result: `HTTP 401`
- response: `missing Authorization header`
- outcome: unauthorized access is rejected

### Post-Deploy Conclusion

After deploying commit `af39648`, the production hosted-signer flow now works end-to-end:

- full attestation login
- session token exchange
- authenticated platform reads
- authenticated platform writes
- action replay rejection
- missing bearer token rejection

## Local Full End-to-End Success

Local test agent:

- name: `codex-local-e2e-20260314-2`
- agent_id: `NmxrTFtXZGqHTH_ekNXbWpEOjTauq-HACdU2FOtfh7s`

### Call Results

1. `pnpm demo:register:challenge`

- result: success
- outcome: local registration challenge created

2. `pnpm demo:register:complete`

- result: success
- outcome: local platform status became `active`

3. `POST http://127.0.0.1:8093/v1/agents/self_register`

- result: `HTTP 200`
- outcome: hosted-signer agent created successfully

4. `POST http://127.0.0.1:8094/auth/challenge`

- result: `HTTP 200`
- outcome: platform login challenge issued successfully

5. `POST http://127.0.0.1:8093/v1/signer/prepare_auth`

- result: `HTTP 200`
- outcome: success
- returned:
  - `session_pubkey`
  - `delegation_token`
  - `signature_by_session`

6. `POST http://127.0.0.1:8093/v1/signer/sign_full_attestation_issue`

- result: `HTTP 200`
- outcome: success

7. `POST http://127.0.0.1:8093/v1/attestations/full/issue`

- result: `HTTP 200`
- outcome: full identity attestation issued successfully

8. `POST http://127.0.0.1:8094/auth/complete`

- result: `HTTP 200`
- outcome: platform session token exchanged successfully
- verified:
  - `identity_mode=full`

9. `GET http://127.0.0.1:8094/me`

- result: `HTTP 200`
- outcome: authenticated session returned successfully
- verified fields:
  - correct `agent_id`
  - `identity_mode=full`
  - `raw_level=L0`
  - `effective_level=L0`
  - `session_pubkey` present

10. `POST http://127.0.0.1:8093/v1/signer/sign_action` for `post`

- result: `HTTP 200`
- outcome: action signature created successfully

11. `POST http://127.0.0.1:8094/posts`

- result: `HTTP 200`
- outcome: post created successfully
- returned id: `post-1`

12. `POST http://127.0.0.1:8093/v1/signer/sign_action` for `comment`

- result: `HTTP 200`
- outcome: action signature created successfully

13. `POST http://127.0.0.1:8094/comments`

- result: `HTTP 200`
- outcome: comment created successfully
- returned id: `comment-1`

14. `GET http://127.0.0.1:8094/feed`

- result: `HTTP 200`
- outcome: feed returned successfully
- verified:
  - 1 post present
  - 1 comment present
  - same agent identity propagated into content

### Negative Tests

15. replay same signed `POST /posts` action

- result: `HTTP 400`
- response: `action nonce already consumed`
- outcome: replay protection works

16. call `GET /me` without bearer token

- result: `HTTP 401`
- response: `missing Authorization header`
- outcome: unauthorized access is rejected

### Local Conclusion

The complete hosted-signer platform chain works locally:

- full attestation login
- session token exchange
- authenticated platform reads
- signed platform writes
- action replay rejection
- auth rejection for missing bearer token

## Local L1 Upgrade Validation

Upgrade email:

- `907982417@qq.com`

Test agent:

- `NmxrTFtXZGqHTH_ekNXbWpEOjTauq-HACdU2FOtfh7s`

### Call Results

1. `POST http://127.0.0.1:8093/v1/signer/sign_upgrade_request`

- result: `HTTP 200`
- outcome: upgrade request signature created successfully

2. `POST http://127.0.0.1:8093/v1/upgrades/requests`

- result: `HTTP 200`
- outcome: L1 upgrade request created successfully
- verified:
  - status became `human_pending`
  - email masked as `9*******7@qq.com`

3. `POST http://127.0.0.1:8093/v1/upgrades/l1/email/send-link`

- result: `HTTP 200`
- outcome: email verification token generated successfully

4. `POST http://127.0.0.1:8093/v1/upgrades/l1/email/verify`

- result: `HTTP 200`
- outcome: agent upgraded to `L1`

5. `POST http://127.0.0.1:8093/v1/attestations/refresh`

- result: `HTTP 200`
- outcome: refreshed public identity attestation now reports `lvl=L1`

6. repeat login flow after upgrade

- result: all steps `HTTP 200`
- outcome: platform session now reports:
  - `identity_mode=full`
  - `raw_level=L1`
  - `effective_level=L1`

### Upgrade Conclusion

The L1 email upgrade flow works locally end-to-end, and the upgraded level is visible after a fresh full login to the platform.

## Root Cause For Production `prepare_auth` Failure

The local codebase contained a bug that explains the observed production behavior when hosted session state is persisted through a pickle-based store:

- `prepare_auth` generated an Ed25519 session private key
- the hosted session record stored the raw `Ed25519PrivateKey` object
- Redis-backed state encoding uses `pickle.dumps(...)`
- `Ed25519PrivateKey` objects are not picklable

Fix implemented locally:

- store hosted session private key as base64url instead of a raw key object
- load the private key only when signing is needed
- add a regression test proving hosted session records are picklable

Relevant files:

- [service.py](/Volumes/ST7/Projects/Rare/services/rare-identity-core/services/rare_api/service.py)
- [test_core.py](/Volumes/ST7/Projects/Rare/services/rare-identity-core/tests/test_core.py)

## Final Status

### Confirmed working

- local platform registration
- production platform registration with real subdomain `rare-demo.rareid.cc`
- hosted-signer agent self-registration
- production full login and session exchange
- production authenticated platform reads and writes
- production replay protection
- production unauthorized request rejection
- local full login and session exchange
- local authenticated platform reads and writes
- local replay protection
- local unauthorized request rejection
- local L1 email upgrade and post-upgrade re-login

### Production issue resolved

Previous production blocker on 2026-03-14:

- `POST https://api.rareid.cc/v1/signer/prepare_auth`
- pre-deploy result: `HTTP 500`

Final status after deploy:

- post-deploy result: `HTTP 200`
- end-to-end production hosted-signer flow: working
