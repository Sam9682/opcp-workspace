# Documents and document adapter

## Document space

The `/documents` page lists published documents grouped by category (docs, links, scripts, trainings). Administrators can upload and delete documents.

Code: `app/documents/router.py`, `app/models/document.py`, `app/services/storage_service.py`, `app/services/document_seed_service.py`.

### Categories and access levels

| Category | Origin |
|----------|--------|
| `docs`, `trainings` | Seeded from `docs/to_publish/docs/` and `docs/to_publish/trainings/` only |
| `scripts` | Seeded from `docs/to_publish/scripts/`, or uploaded `.sh`, `.sql`, `.py` files |
| `links` | Seeded from `docs/to_publish/links/`, or uploaded `.links` files. The file holds a URL on its first line, and the UI shows it as a link |
| `documents` | Uploaded `.pdf`, `.doc`, `.docx`, `.md`, `.txt` files (legacy/default) |

Each document has an access level:

| Access level | Who can see and download it |
|--------------|-----------------------------|
| `public` | everyone, including anonymous users |
| `members` | logged-in users |
| `administrators` | administrators |

### API (`/api/documents`)

| Method | Path | Access | Notes |
|--------|------|--------|-------|
| POST | `/upload` | administrators | Multipart `file` + `access_level`. Category is derived from the extension |
| GET | `?category=` | anyone, filtered by access level | Newest first. `links` entries include `target_url` |
| GET | `/{id}/download` | depends on access level | Increments `download_count`, writes an audit log entry |
| DELETE | `/{id}` | administrators | Deletes the file and the row, writes an audit log entry |

Uploads are stored in `UPLOAD_DIR` (default `./storage/uploads`, the `app_data` volume in Docker). Files are renamed to a UUID. The limit is `MAX_UPLOAD_SIZE` (10 MB), and only the extensions listed above are allowed.

### Publishing from `docs/to_publish`

At each backend start, `seed_docs_folder()` publishes the files found under `DOCS_SEED_DIR` (default `./docs/to_publish`):

```
docs/to_publish/
├── docs/        -> category "docs"
├── links/       -> category "links"  (one URL per file, no extension needed)
├── scripts/     -> category "scripts"
└── trainings/   -> category "trainings"
```

- Only these four subfolders are scanned (recursively). Files directly under `docs/to_publish/` are not published.
- Seeded documents get the `members` access level. The uploader is `admin@opcp-psmc.com`, or the oldest administrator if that account does not exist. Seeding is skipped if there is no administrator.
- Documents are matched by file name. An unchanged file (same SHA-256) is skipped. A changed file replaces the stored copy and keeps its database row.
- Removing a file from the folder does **not** delete the published document; delete it from the UI.
- Files larger than `MAX_UPLOAD_SIZE` are skipped.

`docs/to_publish/` is baked into the backend image, so rebuild the image to publish new files.

## Document adapter

The `/document-adapter` page rewrites a document for a target audience with an AI provider, then exports the result as PDF or Word.

Code: `app/document_adapter/` (`router.py`, `service.py`, `extraction.py`, `prompts.py`, `export.py`).

### Flow

1. Choose a source: a document from the document space, or a newly uploaded PDF/Word file. Uploading goes through `/api/documents/upload`, so only administrators can use upload mode.
2. Choose an audience level:
   - `non_it_beginner`: sales or administrative staff; no jargon, uses analogies.
   - `it_beginner`: defines acronyms, uses short sentences.
   - `it_expert`: concise; assumes cloud and OPCP knowledge.
3. Choose an enabled AI provider (see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md)) and, optionally, add context (≤ 5000 characters).
4. Preview the result and export it.

### API (`/api/document-adapter`, logged-in users)

| Method | Path | Body |
|--------|------|------|
| POST | `/adapt` | `document_id` **or** `uploaded_filename`, `audience_level`, `ai_provider`, `additional_context?` |
| POST | `/export` | `adapted_content`, `source_name`, `audience_level`, `format` (`pdf` or `docx`) |

The exported file is named `<source>__<audience>.<ext>`.

### Supported sources

Text is extracted based on the document's stored MIME type:

- `application/pdf`, extracted with pypdf.
- `.docx` (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`), extracted with python-docx.

Legacy `.doc` files are accepted by the MIME check but python-docx cannot parse them. Seeded `.docx`/`.odt` files are stored as `application/octet-stream` and are rejected (`INVALID_FILE_TYPE`). Upload a `.docx` or PDF instead.

### Errors

| Code | HTTP | Cause |
|------|------|-------|
| `PROVIDER_DISABLED` | 400 | The provider is disabled |
| `INVALID_FILE_TYPE` | 400 | Unsupported source format |
| `DOCUMENT_NOT_FOUND` / `FILE_NOT_FOUND` | 404 | Unknown document, or its file is missing |
| `PROVIDER_AUTH_ERROR` | 502 | Bad or missing provider credentials |
| `ADAPTATION_ERROR` | 500 | Any other failure |
