# Video Workbench Full Module Design

## Purpose

Upgrade the current short-video generation project from a command-line and chat demo into a usable video production workbench. The same release includes every module from the reference checklist, while separating locally runnable functionality from external provider integrations that need later credentials or business systems.

The product should feel like a professional creator operations console, not a demo page. It must avoid "demo" and "MVP" language in the user interface, and it must not use a phone-frame preview.

## Source Inputs

- Reference image: feature delivery checklist with modules for assets, tasks, intelligent editing, lens controls, material processing, screen processing, quality enhancement, watermark region processing, subtitles, voiceover, account membership, payment backend, and provider APIs.
- Lark document URL was provided but could not be fetched because local `lark-cli` is not configured. The design therefore uses the reference image and the existing codebase as the authoritative inputs for this implementation pass.

## Current System

The repository already includes:

- FastAPI service in `app/api.py`.
- Chat harness in `app/harness.py`.
- Script and shot planning in `app/script_writer.py`, `app/story_pipeline.py`, and `app/planner.py`.
- Image and video provider clients in `app/image_generator.py` and `app/generator.py`.
- FFmpeg assembly in `app/assembler.py`.
- Batch generation in `app/batch_pipeline.py`.
- A simple CDN-based chat UI in `app/chat_ui.html`.
- A Vite React frontend in `frontend/`.

The implementation should use the Vite React frontend as the main product surface. The CDN chat UI can remain for compatibility, but it is not the primary workspace.

## Scope

This release includes all checklist modules in one product surface:

- Asset and task management.
- Intelligent editing and mixing.
- Random lens and sweep-light controls.
- Material processing.
- Screen processing.
- Quality enhancement.
- Watermark region processing.
- Subtitles.
- Voiceover.
- Account and membership.
- Payment and admin backend.
- Provider API integration points.

## Delivery Boundary

Runnable in this release:

- Local task, asset, user, membership, order, and configuration records.
- Task creation and status tracking.
- Story-to-scenes and scenes-to-shots planning using existing pipeline code.
- Batch task records and progress summaries.
- FFmpeg-backed processing command construction and supported local operations.
- Subtitle text editing, timeline data, SRT export, and optional subtitle burn-in command path.
- Voiceover configuration records and provider abstraction with mock audio output.
- Membership and order management views backed by local persistence.
- Admin configuration views for users, members, orders, tasks, and provider settings.

Reserved behind adapters:

- Real payment channel callbacks.
- Real login and identity provider.
- Real TTS generation.
- Real speech recognition.
- Real super-resolution, frame interpolation, and face restoration providers.
- Real watermark removal provider.
- Cloud storage or CDN distribution.

Watermark handling must be represented as user-configured region processing only: crop, blur, mask, or cover operations. The UI and API must not promise universal watermark removal.

## Architecture

### Backend Modules

Add or extend these modules:

- `app/models.py`: domain dataclasses or Pydantic models for assets, workbench tasks, edit profiles, lens settings, subtitle cues, voiceover settings, membership plans, orders, users, and provider configuration.
- `app/task_store.py`: local JSON persistence with CRUD methods for all workbench records. It should create its storage directory automatically and write deterministic JSON.
- `app/video_ops.py`: FFmpeg operation planning. It should build commands for crop, scale, speed, mirror, mute, transcode, extract frames, subtitle burn-in, and concat. Command construction should be testable without requiring FFmpeg execution for most tests.
- `app/providers.py`: provider interfaces and mock adapters for video generation, image generation, voiceover, subtitle recognition, payment, and quality enhancement.
- `app/api.py`: add workbench API endpoints while preserving existing chat and plan endpoints.

### Frontend Modules

Use `frontend/src/App.jsx` as the main shell and split into smaller components if useful:

- Navigation shell with module tabs.
- Asset and task dashboard.
- Intelligent edit controls.
- Lens and sweep-light controls.
- Material processing controls.
- Screen processing controls.
- Quality enhancement controls.
- Watermark region controls.
- Subtitle editor.
- Voiceover panel.
- Account and membership panel.
- Payment and admin panel.
- Provider integration panel.
- Right-side task status and output panel.

The interface should be dense, clear, and work-focused. It should use forms, sliders, toggles, segmented controls, tables, status chips, and download links. It should avoid landing-page composition, oversized hero sections, and decorative gradients.

## API Design

New endpoints:

- `GET /api/workbench/state`: returns assets, tasks, membership, orders, provider configs, and defaults.
- `POST /api/assets`: creates an asset record from file metadata or a local path.
- `GET /api/assets`: lists assets.
- `POST /api/tasks`: creates a workbench generation or processing task.
- `GET /api/tasks`: lists tasks.
- `GET /api/tasks/{task_id}`: reads a task detail.
- `POST /api/tasks/{task_id}/run`: runs the locally supported task pipeline.
- `POST /api/tasks/{task_id}/cancel`: marks a pending or running task as cancelled when possible.
- `GET /api/tasks/{task_id}/download`: downloads a generated MP4 or manifest when available.
- `POST /api/subtitles/srt`: converts subtitle cues to SRT text.
- `POST /api/voiceovers`: creates a voiceover job record and mock output.
- `GET /api/membership`: reads local membership state.
- `POST /api/orders`: creates a local order record.
- `GET /api/admin/summary`: returns user, task, order, and quota summary.
- `PUT /api/admin/provider-config`: updates local provider configuration.

Existing endpoints remain:

- `POST /api/chat`
- `POST /api/chat/stream`
- `POST /api/plan`
- `GET /api/health`

## Data Model

Core records:

- `Asset`: `id`, `name`, `type`, `source`, `path`, `duration_seconds`, `resolution`, `created_at`, `metadata`.
- `WorkbenchTask`: `id`, `title`, `status`, `module`, `story_prompt`, `asset_ids`, `edit_profile`, `subtitle_cues`, `voiceover`, `progress`, `outputs`, `error`, `created_at`, `updated_at`.
- `EditProfile`: lens, material, screen, quality, watermark, subtitle, voiceover, export, and batch options.
- `SubtitleCue`: `index`, `start_ms`, `end_ms`, `text`.
- `VoiceoverConfig`: `voice`, `speed`, `pitch`, `language`, `text`, `audio_path`.
- `MembershipState`: `user_id`, `plan`, `valid_until`, `quota_total`, `quota_used`, `features`.
- `OrderRecord`: `id`, `user_id`, `plan`, `amount`, `currency`, `status`, `provider`, `created_at`.
- `ProviderConfig`: `kind`, `provider`, `enabled`, `model_name`, `base_url`, `has_token`.

## Task Execution Flow

1. The frontend submits a task with story, assets, module settings, subtitles, and voiceover options.
2. The backend stores the task with `pending` status.
3. `POST /api/tasks/{task_id}/run` switches the task to `running`.
4. For story generation tasks, the backend reuses `SceneStoryboardPipeline`, `VideoGenerationClient`, and `VideoAssembler`.
5. For processing-only tasks, the backend builds FFmpeg commands through `video_ops.py` and writes outputs under `output/workbench/<task_id>/`.
6. The task store updates progress, output paths, and error details.
7. The frontend polls task state and exposes previews, manifests, and downloads.

Long-running production queues are out of scope. The first implementation can run synchronously behind the run endpoint while preserving task state for later background workers.

## Error Handling

- API validation failures return 422 with field-level details.
- Missing assets, missing outputs, and unsupported local operations return 404 or 400.
- Provider credentials are never exposed; state only returns `has_token`.
- External provider failures are stored in the task `error` field.
- Unsupported reserved features should return explicit `unsupported_provider` or `not_configured` messages instead of failing silently.

## Testing

Backend:

- Model serialization and validation tests.
- `TaskStore` CRUD and deterministic persistence tests.
- `video_ops.py` command construction tests for each supported FFmpeg operation.
- API tests for state loading, asset creation, task creation, SRT export, order creation, admin summary, and provider config updates.

Frontend:

- Component rendering tests for the main navigation and key panels.
- Interaction tests for task creation form, subtitle editing, and admin/provider configuration.
- Build verification with Vite.

Validation commands:

- `python -m pytest`
- `npm --prefix frontend test -- --run`
- `npm --prefix frontend build`

If the current project lacks test tooling, add the smallest appropriate test setup needed to execute these tests.

## Acceptance Criteria

- The frontend opens as a full workbench with all reference modules represented.
- Users can create assets and tasks through the UI.
- Users can configure editing, lens, material, screen, quality, watermark region, subtitle, voiceover, export, membership, order, admin, and provider settings.
- Task records persist locally and survive service restart.
- At least one generation or processing path can run end to end with local or mock providers.
- SRT export works from subtitle cues.
- Backend tests and frontend build pass.
- No UI text describes the product as a demo or MVP.
- Existing chat and plan APIs continue to work.
