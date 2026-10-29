# FastAPI Lead Management API

A REST API built using FastAPI and PostgreSQL for managing leads.

This project supports CRUD operations, search, filtering, pagination, and duplicate email validation.
## Features

- Create a new lead
- Get all leads
- Get a single lead by ID
- Update lead details
- Delete a lead
- Search leads by name and email
- Filter leads by status and source
- Pagination support
- Duplicate email validation
- Exact duplicate protection for nurture content
- 404 error handling
- Swagger API documentation

## Nurture content deduplication

Nurture content is normalized before identity comparison. Text uses SHA-256
after normalizing line endings and trimming surrounding whitespace. Article
identities include canonical source URLs and stable content IDs, image
identities can use stable image IDs, canonical URLs, or content hashes, and
batch updates use stable batch IDs. Used identities are associated with each
generated nurture message in `nurture_content_identities`; the table is
created and upgraded through the Alembic migration chain.

The nurture selector prefers an approved item that has not already been used
for that lead. If the approved set has no alternative, it retains the existing
first-item fallback. Previously generated and sent text messages are included
in duplicate checks, including legacy messages created before identity
tracking was added. Image selection returns no image when every approved image
is already used.

RSS/Atom article feeds are configured with semicolon-separated environment
variables named for the topic, for example
`RSS_FEEDS_AWS_CLOUD_ENGINEERING` and
`RSS_FEEDS_AZURE_CLOUD_ENGINEERING`. Set each variable to an approved feed URL
on a domain already allowed for that topic in `ai/verified_content.py`; no
feed URL is assumed by the application. Feed entries are accepted only when
they contain a title, link, summary, and publication date, the linked article
is from a trusted domain, and it is within the existing 30-day freshness
window. Identical entries within configured feeds are collapsed by canonical
article URL or summary hash before per-lead history filtering.

If no feed is configured, the API continues to return the existing
`verified_content_required` not-ready result. If a configured feed is
untrusted, unavailable, too large, or invalid XML, the nurture endpoint
returns HTTP 503 rather than sending unverified fallback content. Image and
batch items still require their own approved sources.

## HOT lead sales alerts

The root FastAPI app creates one persistent `hot_lead` alert when a lead
transitions from non-HOT to HOT through either CRM scoring (`lead_score` /
`lead_temperature`, HOT at 70) or AI qualification scoring (`ai_score` /
`ai_temperature`, HOT at 80). A lead is considered HOT if either temperature
is HOT, and an existing active alert suppresses duplicates. Alerts include
the lead, triggering score and reason, available qualification details,
status (`active`, `acknowledged`, or `resolved`), and creation timestamp.

The API provides `GET /alerts` (optional `status`, `skip`, and `limit`
filters), `GET /alerts/{alert_id}`, and
`PATCH /alerts/{alert_id}/status` with a JSON body such as
`{"status":"acknowledged"}`. The dashboard reads these endpoints from
`NEXT_PUBLIC_API_URL` and offers acknowledge/resolve actions in the HOT Lead
Alerts panel.

The `lead_alerts` table already exists in the initial schema. Revision
`0003_hot_lead_alert_details` adds the reason, score, and qualification
summary columns and normalizes legacy alert statuses. Apply `alembic upgrade
head` only after verifying that Alembic is configured for the intended
database; application startup does not run migrations.

Approved images are loaded from `ai/approved_images.json` by default. To use a
separate manifest, set `APPROVED_IMAGE_MANIFEST` to its path. The manifest is a
JSON array of records with `image_id` or `image_url`, `topic`, `source`, and
`approved: true`; records not explicitly approved are ignored. An optional
`file_path` is resolved relative to the manifest, must remain inside its
directory, and is SHA-256 hashed. An optional supplied `content_hash` must
match that file or be a valid SHA-256 digest. URLs are canonicalized before
identity checks. Selected image IDs, canonical URLs, topics, sources, approval
state, and available hashes are stored alongside the nurture record. The
default manifest is empty; configure only actual approved image metadata.

Approved batches are loaded from `ai/approved_batches.json` by default. Set
`APPROVED_BATCH_MANIFEST` to use another JSON manifest path. Each approved
record requires `approved: true`, a topic, source, and non-empty `message`,
`summary`, or `text`. Provide a stable `batch_id`, or provide `batch_name` and
an ISO `start_date` (`YYYY-MM-DD`) to derive a deterministic SHA-256-based ID.
Unapproved records are ignored. Batch candidates make the existing engagement
selector eligible to prioritize a batch update; a previously used batch is
skipped when an unused approved alternative exists. Selected batch IDs and
content hashes are persisted in `nurture_content_identities`, without needing
a separate batch table or migration. The default manifest contains no batch
data; populate it only with real, approved batch information.

## Database migrations and concurrent nurture requests

Database schema changes are managed with Alembic; the API modules no longer
create or alter tables during import. Both API processes and Alembic use the
same root `.env`; `ai/.env` is not loaded. Process environment variables take
precedence over the root `.env`, allowing production secrets and connection
settings to be supplied by the deployment environment. Set either
`DATABASE_URL` or `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and
`DB_NAME`. `DB_HOST` defaults to `localhost` for local development. Keep
credentials out of source control. Configure the intended database before
running `alembic upgrade head`.

For an existing database created by the former `create_all()` startup path,
back up the database and verify that its core tables match revision
`0001_initial_schema` before recording that baseline with
`alembic stamp 0001_initial_schema`. Then run `alembic upgrade head` to add
the content identity and image metadata tables and indexes. The second
migration refuses to add unique indexes if existing identity or image metadata
rows contain duplicates; it does not delete or rewrite existing rows. Resolve
any such conflict explicitly after reviewing the affected records, then rerun
the migration. Do not run `alembic stamp` on a database whose core schema has
not been checked. Run and verify migrations in staging before production;
application startup does not run migrations automatically.

Nurture generation locks the corresponding lead row with PostgreSQL
`SELECT ... FOR UPDATE` while it checks same-day history, selects content,
and persists the nurture and identities. A unique per-lead content identity
index provides an additional database guard. All code paths that create a
nurture must use the same service/locking protocol. Requests for a single lead
are serialized, including while a configured article feed is fetched; requests
for different leads remain independent.
## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- Uvicorn
- Postman
- Git & GitHub
## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /leads | Create a new lead |
| GET | /leads | Get all leads |
| GET | /leads/{lead_id} | Get a single lead |
| PUT | /leads/{lead_id} | Update a lead |
| DELETE | /leads/{lead_id} | Delete a lead |
## Search, Filter and Pagination

### Filter by Status
GET /leads?status=new

### Filter by Source
GET /leads?source=Instagram

### Search by Name
GET /leads?name=Irfan

### Search by Email
GET /leads?email=gmail.com

### Pagination
GET /leads?skip=0&limit=5

### Combined Filter
GET /leads?status=new&source=Instagram
## How to Run the Project

1. Clone the repository

   git clone https://github.com/skillectleadnuturing27-afk/skillect.git

2. Open the project folder

   cd skillect

3. Install required packages

   pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv

4. Create a `.env` file and configure PostgreSQL database credentials.

5. Start the FastAPI server

   uvicorn main:app --reload

6. Open Swagger API documentation

   http://127.0.0.1:8000/docs

## API Documentation

After starting the server, Swagger UI is available at:

http://127.0.0.1:8000/docs

## Project Status

Backend MVP completed with CRUD operations, validation, filtering, search and pagination.
