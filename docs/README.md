# Documentation

## Project documentation

| Document | Content |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, startup sequence, scheduled jobs, roles, API reference, data model, frontend routes |
| [CONFIGURATION.md](CONFIGURATION.md) | All environment variables |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker Compose stack, `deployApp.sh`, ports, TLS, nginx, local development, migrations |
| [OPERATIONS.md](OPERATIONS.md) | Database access, backups (local and S3/OVH), restore, admin recovery, logs |
| [SECURITY.md](SECURITY.md) | Authentication, 2FA, rate limits, audit log, GDPR, field encryption |
| [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md) | Oracle AI assistant: providers, RAG companion, ingestion, API |
| [DOCUMENTS.md](DOCUMENTS.md) | Document space, publishing from `to_publish/`, document adapter |
| [PAYMENTS.md](PAYMENTS.md) | Stripe/PayPal membership payments (backend only) |

Script-level details are in [`scripts/README.md`](../scripts/README.md) and [`scripts/README_BACKUP.md`](../scripts/README_BACKUP.md).

## Content folders

These folders hold content used by the application, not documentation about it:

| Folder | Used by |
|--------|---------|
| [`to_publish/`](to_publish/) | Published into the document space at every backend start (`docs/`, `links/`, `scripts/`, `trainings/` subfolders), see [DOCUMENTS.md](DOCUMENTS.md#publishing-from-docsto_publish) |
| [`opcp_external_docs/`](opcp_external_docs/) | OPCP product reference material (architecture notes, runbooks, milestones and milestone prompts) that `conf/shai_context.md` tells the Shai provider to use. **Stored encrypted**; the backend decrypts it with `KEY_DECRYPT_INFORMATIONS_OPCP`, and `scripts/opcp_docs_crypto.py` decrypts and re-encrypts it for editing (see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md#encrypted-opcp-reference-documentation)) |
| [`OPCP_First_Steps.md`](OPCP_First_Steps.md) | Customer-facing OPCP first-steps guide |

## RAG ingestion note

`scripts/ingest_embeddings.py` indexes every `*.md` file **directly** under `docs/`, which includes the documents above. Content you want the OPCP Companion to answer from belongs at this level, or as PDFs directly under `docs/to_publish/`. See [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md#ingesting-documents).
