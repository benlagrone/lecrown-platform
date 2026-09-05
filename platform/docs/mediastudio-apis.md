# MediaStudio API Inventory

`MediaStudio` should be treated as an external media platform that `lecrown-platform` can call over HTTP.

This is the working assumption for now:

- `lecrown-platform` owns content, tenants, distribution decisions, CRM, and publishing triggers.
- `MediaStudio` owns media generation, rendering, narration, music, and related production pipelines.
- Integration should happen through API clients and environment-configured base URLs, not direct script imports.

## Current Position

The `MediaStudio` workspace at `/Users/benjaminlagrone/Documents/projects/MediaStudio` already contains multiple services that can be used as backends.

For `lecrown-platform`, the important framing is:

- `MediaStudio` is not a single app.
- It is a suite of callable services.
- We should prefer a small number of stable HTTP integration points instead of coupling to internal scripts.

## Primary API Candidates

### 1. `rs-video-stitch` render API

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/rs-video-stitch`

What it is:

- A proper render backend with a FastAPI app, SQLite-backed jobs, a worker process, shared storage, and output retrieval.

Why it matters:

- This is the cleanest fit for the long-term `lecrown-platform -> worker -> artifact` architecture.
- It already separates API and worker responsibilities.

Documented surface:

- `PUT /v1/projects/{projectId}/scenes`
- `POST /v1/projects/{projectId}/assets`
- `POST /v1/projects/{projectId}/render`
- `GET /v1/jobs/{jobId}`
- `GET /v1/projects/{projectId}/outputs`
- `GET /v1/projects/{projectId}/outputs/video`

Default network shape:

- Host port `8082`
- Shared Docker network: `fortress-phronesis-net`

Recommended use:

- Treat this as the preferred render worker target for `lecrown-platform`.

### 2. `video-gen`

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/video-gen`

What it is:

- A higher-level FastAPI pipeline that covers project init, parsing, narration, image generation, video generation, music overlay, and upload.

Why it matters:

- This is the fastest way to get an end-to-end media pipeline behind one API.
- It is broader and less narrowly scoped than `rs-video-stitch`.

Documented surface:

- `GET /settings`
- `POST /init-project`
- `POST /parse-text`
- `POST /parse-verse`
- `POST /generate-narration`
- `POST /generate-images`
- `POST /generate-video`
- `POST /api/overlay-music`
- `POST /upload-video`
- `POST /cleanup-narration`

Default network shape:

- Host port `8001`
- Shared Docker network: `fortress-phronesis-net`

Recommended use:

- Treat this as the faster integration target when we want one service to handle more of the pipeline.

## Supporting API Services

### `audio_xtts`

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/audio_xtts`

Role:

- Text-to-speech and voice inventory.

Endpoints:

- `GET /api/voices`
- `POST /api/tts`

Default port:

- `5002`

Use case:

- Support narration generation directly or through render services that already know how to call xTTS.

### `musicService`

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/musicService`

Role:

- MusicGen-based background music generation.

Endpoint:

- `POST /generate-music/`

Default port:

- `7000`

Use case:

- Optional soundtrack generation for longer-form or branded video outputs.

## Reference Clients and Non-Targets

### `video-script`

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/video-script`

Role:

- Client/orchestrator that calls other HTTP services.

How to treat it:

- Use it as reference logic for payload shapes, real-estate content flow, and prompt orchestration.
- Do not treat it as the service boundary for `lecrown-platform`.

### `video-client`

Path:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/video-client`

Role:

- Frontend UI.

How to treat it:

- Not a backend integration target.

### Image-generation stacks

Relevant paths:

- `/Users/benjaminlagrone/Documents/projects/MediaStudio/stable-diffusion-webui`
- `/Users/benjaminlagrone/Documents/projects/MediaStudio/stable-diffusion-webui2`
- `/Users/benjaminlagrone/Documents/projects/MediaStudio/phronesis-image-orchestrator`

How to treat them:

- These sit behind the video pipelines.
- `lecrown-platform` should avoid talking to them directly unless we intentionally want lower-level image orchestration.

## Current Recommendation for LeCrown

For now, document the integration options this way:

1. Preferred render worker API: `rs-video-stitch`
2. Fastest all-in-one pipeline API: `video-gen`
3. Supporting narration API: `audio_xtts`
4. Supporting music API: `musicService`

## Integration Rules

- `lecrown-platform` should call `MediaStudio` over HTTP.
- Base URLs should be environment-configured.
- File-path assumptions should be avoided unless both systems share storage.
- If a service returns a URL, prefer the URL contract over host-local file paths.
- `video-script` should inform integration design, not become the integration point.

## Near-Term Implementation Direction

When `lecrown-platform` is ready to use `MediaStudio` for production:

1. Add environment variables for `MEDIASTUDIO_RENDER_API_URL`, `MEDIASTUDIO_VIDEO_GEN_URL`, `MEDIASTUDIO_XTTS_URL`, and `MEDIASTUDIO_MUSIC_URL`.
2. Point the current video client abstraction at one chosen backend first.
3. Keep the `lecrown-platform` distribution layer agnostic so the backend target can switch from `video-gen` to `rs-video-stitch` without changing content logic.
