# LeCrown Platform

Multi-tenant backend and admin surface for:

- `lecrowndevelopment.com`
- `lecrownproperties.com`

The platform keeps content, transformation, distribution, and inquiry handling inside one codebase with a required tenant value of `development` or `properties`.

## Structure

```text
backend/
docs/
frontend/
docker-compose.yml
.env.example
README.md
```

## What is implemented

- FastAPI backend with tenant-aware `content`, `inquiry`, `linkedin`, `youtube`, `distribution`, and `auth` routes
- SQLite persistence through SQLAlchemy
- Minimal React admin for creating canonical content, choosing output channels, and viewing property inquiries
- Transform layer that adapts one content record into channel-specific payloads
- LinkedIn publish service wired to tenant-specific organization IDs
- YouTube upload service wired for per-tenant OAuth access or refresh tokens
- Video worker client that can call a separate render server over HTTP or run in stub mode

## API overview

- `POST /content/create`
- `GET /content/list?tenant=development|properties`
- `POST /inquiry/create`
- `GET /inquiry/list`
- `POST /linkedin/publish`
- `POST /youtube/publish`
- `POST /distribution/publish`
- `POST /auth/login`
- `GET /auth/me`
- `GET /healthz`

## Local run

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend/admin
npm install
npm run dev
```

The admin app defaults to `http://localhost:8000` for the API.

Copy `.env.example` to `.env` before running the stack locally.

## Content model shape

Canonical content is stored once and carries distribution intent plus media state:

```json
{
  "tenant": "development",
  "type": "insight",
  "title": "Why warehouse operations break down",
  "body": "Communication failures create delays and cost leakage.",
  "tags": ["operations", "industrial"],
  "distribution": {
    "linkedin": true,
    "youtube": true,
    "website": true,
    "twitter": false
  },
  "media": {
    "video_generated": false,
    "video_path": "/videos/warehouse.mp4",
    "video_url": null,
    "render_status": null,
    "render_job_id": null,
    "youtube_video_id": null,
    "youtube_status": null
  }
}
```

## Docker run

```bash
docker compose up --build
```

Backend: [http://localhost:8000](http://localhost:8000)

Frontend: [http://localhost:3000](http://localhost:3000)

## Distribution flow

The platform now follows:

```text
content -> transform -> distribute
```

Current channel support:

- `linkedin`: implemented
- `youtube`: implemented
- `website`: placeholder response in the distribution controller
- `twitter`: stub publisher placeholder

Video generation ownership:

- The API orchestrates render requests.
- A separate worker is expected to produce the video.
- The backend can call that worker over HTTP through [backend/app/services/video_client.py](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/backend/app/services/video_client.py).

## MediaStudio APIs

`MediaStudio` is now documented as an external API suite that `lecrown-platform` can use for media generation and rendering.

See:

- [docs/mediastudio-apis.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/mediastudio-apis.md)

Current stance:

- preferred render worker target: `rs-video-stitch`
- faster all-in-one media backend: `video-gen`
- supporting narration backend: `audio_xtts`
- supporting music backend: `musicService`

## First milestone flow

1. Create a content item through `POST /content/create` or the admin UI.
2. Confirm it was stored with `GET /content/list?tenant=...`.
3. Set `LINKEDIN_TOKEN` plus the tenant org IDs in `.env`.
4. Publish with `POST /linkedin/publish`.
5. Verify the post on the matching LinkedIn organization page.

## YouTube publish flow

Use one of these credential paths per tenant:

- Set `YOUTUBE_ACCESS_TOKEN_DEV` or `YOUTUBE_ACCESS_TOKEN_PROP` directly.
- Or set `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and the tenant refresh token so the backend can mint an access token at publish time.

Example direct upload:

```json
{
  "tenant": "development",
  "title": "Why warehouse operations break down",
  "description": "A direct explanation of the operational failure pattern.",
  "video_path": "/videos/warehouse.mp4",
  "tags": ["property management", "warehouse"]
}
```

Example orchestrated distribution:

```json
{
  "content_id": "123",
  "channels": ["linkedin", "youtube"],
  "video_style": "corporate_clean",
  "youtube_video_path": "/videos/warehouse.mp4"
}
```

If `youtube_video_path` is omitted, the distribution service will ask the video worker to render one.

## Video worker integration

By default the platform runs in `VIDEO_RENDER_MODE=stub`, which is the safe development path while the worker contract is still being finalized.

To use an HTTP render worker:

1. Set `VIDEO_RENDER_MODE=http`
2. Set `VIDEO_SERVER_URL` to the worker base URL
3. Optionally change `VIDEO_RENDER_ENDPOINT` and `VIDEO_RENDER_DEFAULT_STYLE`

Expected worker request:

```json
{
  "content_id": "123",
  "script": "Why warehouse operations break down...",
  "title": "Why warehouse operations break down",
  "tenant": "development",
  "style": "corporate_clean",
  "tags": ["operations", "industrial"]
}
```

Expected worker response:

```json
{
  "status": "complete",
  "job_id": "job_123",
  "video_path": "/shared/outputs/video_123.mp4",
  "video_url": "http://100.x.x.x:8001/files/video_123.mp4"
}
```

Notes:

- `video_path` only works if the platform can read that path locally or via a shared mount.
- `video_url` is the safer cross-machine contract; the backend will download it temporarily before uploading to YouTube.
- Tailscale is the simplest way to make the worker reachable without exposing it publicly.

## Example payloads

### Create content

```json
{
  "tenant": "development",
  "type": "linkedin_post",
  "title": "A sharper acquisition lens",
  "body": "We underwrite deals by pressure-testing downside first.",
  "tags": ["acquisitions", "strategy"],
  "publish_linkedin": true,
  "publish_site": true
}
```

### Create inquiry

```json
{
  "tenant": "properties",
  "asset_type": "multifamily",
  "location": "Houston, TX",
  "problem": "Occupancy dropped after deferred maintenance piled up.",
  "contact_name": "Jordan Smith",
  "email": "jordan@example.com",
  "phone": "713-555-0199"
}
```

## Notes

- Inquiry capture is restricted to the `properties` tenant.
- Auth exists as a thin admin stub. Content and inquiry routes are not gated yet.
- `ai_video_service.py` now orchestrates remote rendering through `video_client.py` instead of assuming the API renders media itself.
- In `stub` mode, you still need to provide a usable `VIDEO_STUB_VIDEO_PATH`, `VIDEO_STUB_VIDEO_URL`, or a manual `youtube_video_path` if you want YouTube upload to succeed end-to-end.
