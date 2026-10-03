# Person 3 - Frontend Dashboard

This is the third team member's Next.js/React deliverable for the AI Lead Nurturing MVP. It provides an admin view of lead data, statuses, scores, and saved conversations.

## Run locally

1. Open a terminal in this folder.
2. Run `npm install`.
3. Copy `.env.example` to `.env.local`.
4. Run `npm run dev` and open `http://localhost:3000`.

With no `NEXT_PUBLIC_API_URL`, the dashboard presents included demo leads. For the integrated version, set it to the FastAPI host (for example `http://localhost:8000`).

## Backend API contract

The frontend expects the backend owner to implement these CORS-enabled endpoints:

```text
GET /api/leads          -> Lead[]
GET /api/leads/{id}     -> Lead
```

Each `Lead` must contain `id`, `name`, `email`, `phone`, `source`, `status`, `score`, `created_at`, and `conversations`. `status` is one of `new`, `contacted`, `qualified`, `hot`, or `closed`. Each conversation has `id`, `sender` (`lead` or `ai`), `message`, and `created_at`.

The dashboard deliberately keeps scoring and AI logic on the backend/AI module; it only renders the shared API data.
