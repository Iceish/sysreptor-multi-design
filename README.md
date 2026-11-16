# Multi-Design Outputs

A self-hosted **SysReptor server/frontend plugin**. Write one project, then generate a technical report PDF and a presentation PDF using existing compatible designs. No project duplication, design switching, content conversion, stored API tokens, or reptor subprocesses.

The first version includes an **Outputs** project menu, saved labeled choices, editable download filenames, compatibility diagnostics, progress, retry, render warnings, and the official PDF viewer. Each action generates one PDF from the latest saved content.

## Supported platform

Implemented against SysReptor main **`6b0b1fcf7cae6f9e8d308dfda0516dab7a0cd787`**, inspected 2026-11-15. PostgreSQL is required. Plugin hooks are official; the rendering and permission services are internal and require this pin. **The older `2026.97` release is not supported unmodified**: its permission API differs. Community and Professional editions can load this plugin (`professional_only=False`); no Professional-only feature is required. Normal upstream user/license limits still apply. Automated tests use upstream's Professional test configuration; the packaged Community edition also passed the automated browser smoke flow. The full manual walkthrough and exhaustive role/edition matrix remain outstanding.

Upstream pins, research, and the implementation plan are in [docs/PLAN.md](docs/PLAN.md) and [upstream.env](upstream.env). This is a separate custom-plugin repository; SysReptor core and sibling projects are not edited.

## Local Docker development

Requires Git, Python 3, Docker Engine with Compose v2, network access, and enough disk/RAM to build upstream Chromium, Python, and frontend dependencies. The build extends a locally built pinned upstream image using the [official custom-plugin example](https://github.com/Syslifters/sysreptor-plugin-example) structure. No credentials are checked in.

```bash
./scripts/dev.sh init       # generate ignored .env.dev; fetch exact upstream source
./scripts/dev.sh build      # build pinned upstream, then the custom plugin image
./scripts/dev.sh up         # localhost only: http://127.0.0.1:8800
./scripts/dev.sh check
./scripts/dev.sh test
./scripts/dev.sh smoke      # seed synthetic local data; exercise browser/download/error/retry
```

`init` refuses to overwrite a dirty upstream checkout. `.env.dev` is created with mode 0600 and random local database/Django secrets. The local environment uses plaintext storage, matching upstream's fallback; configure upstream encryption/storage and TLS for an actual installation. `down` stops only this Compose project and preserves its volumes.

Create a local user interactively (password input is hidden):

```bash
read -rsp 'Local demo password (15+ characters): ' DJANGO_SUPERUSER_PASSWORD
export DJANGO_SUPERUSER_PASSWORD
docker compose --env-file .env.dev exec -e DJANGO_SUPERUSER_PASSWORD app \
  python3 manage.py createorupdateuser --username demo --superuser
unset DJANGO_SUPERUSER_PASSWORD
./scripts/dev.sh demo --username demo
```

Open [the local server](http://127.0.0.1:8800), sign in, open **SYNTHETIC Multi-Design Demo → Outputs**. The explicit demo command creates a new synthetic project and two designs each time; it never runs at startup. See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

Build the frontend separately with Node 24:

```bash
(cd sysreptor-src/packages && npm ci)
(cd custom_plugins/multidesign/frontend && npm ci && npm run typecheck && npm run generate)
```

The plugin extends `@sysreptor/plugin-base-layer` and imports its `Pdf` component. `static/` is generated, ignored by Git, and included in the Docker image. Both upstream and plugin npm lockfiles are used. Do not copy a source-only plugin directory without building these assets.

## Installing on an existing self-hosted instance

1. Back up the database and files and verify the exact upstream commit. Build the plugin image above, or include the built `custom_plugins/multidesign` directory in your own image based on that commit.
2. Add `/custom_plugins` to the existing comma-separated `PLUGIN_DIRS`. Preserve any existing paths and other custom plugins. The supplied image defaults to `/app/plugins,/custom_plugins`.
3. Append `multidesign` to your existing `ENABLED_PLUGINS` list. Its stable plugin ID is `d42d1b7f-9c3b-4a62-a3f9-2d070d560127`.
4. Run `python3 manage.py migrate`, then restart server/workers and reload the browser. The supplied local startup runs migrations automatically. The plugin creates only its own configuration/lease tables.
5. Ensure `/static/plugins/<plugin-id>/index.html` and `plugin.js` are served. Pinned upstream uses `WHITENOISE_USE_FINDERS=True`; external static hosting requires collecting/copying plugin files too.

No token entry or additional login is required. The plugin iframe uses the normal same-origin session. Endpoints are under `/api/plugins/<plugin-id>/api/projects/<project-id>/outputs/` (GET/PUT) and `render/` (POST).

## Usage

Choose the current design or another visible design, enter a label such as **Technical report** or **Presentation**, and save it. Select **Generate PDF** to preview the result. Edit the filename and download the same generated bytes. Re-render after editing source content. Changing designs clears the old preview so it cannot be mistaken for the new output.

The server checks project read access and selected-design use/visibility on every endpoint, inside the snapshot, and before delivering a PDF. It uses the same design queryset as upstream's design-selection serializer. It does not grant design editing, export, or project membership. As with upstream project preview/generate, project read access permits PDF rendering, including read-only projects. Saving choices requires `project.update_settings` and a project that is not read-only. An inaccessible saved design is hidden; saving the visible list replaces hidden choices too, with an explicit UI warning.

The endpoints use upstream session authentication, CSRF behavior and PDF throttling (`pdf`, normally 3 actions/10 seconds). SysReptor's custom CSRF middleware exempts JSON/non-POST requests because cross-origin use requires preflight. This plugin accepts JSON only and sends the CSRF header if a cookie exists. It does not exempt its own views or enable cross-origin access.

## Content, schemas, and lifecycle

The target design's field IDs/types must be a subset of the source schema. Validation walks report and finding objects/list items recursively, requires all target fields even when optional, and ensures all source enum choices exist in the target. JSON schemas, CVSS versions, number bounds, and string patterns must match. Unknown types fail closed. Labels, defaults, required flags, ordering, and unused source fields may differ; this is schema compatibility, not report completeness checking. There is no forced conversion. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The plugin captures a PostgreSQL repeatable-read, read-only snapshot of saved report/finding/member data, selected design HTML/CSS/schema/assets, and referenced project image bytes. Only collection runs inside the transaction; the long render runs outside it. Later edits appear on the next action. Storage is not transactional: deletion/unavailability during collection fails safely and can be retried. File attachments remain unchanged; as in upstream rendering, arbitrary attached files are not embedded automatically.

Formatted content/resources exist in request/task memory and the normal upstream task transport. The PDF is returned with `no-store` and held in browser memory for preview/download, never stored by plugin models. Existing server task/backend retention still applies. Configuration stores only project, label, design UUID, filename as ordinary, unencrypted plugin metadata; avoid putting report content or credentials in labels/filenames. Configuration and leases cascade on project deletion; normal project export/import does not transfer plugin preferences.

A per-project/per-user lease rejects accidental duplicate render submissions with HTTP 409. Different users/projects can render independently. Token-scoped `finally` cleanup runs on success, handled errors, and cancellation. If the worker crashes, the next request for that user/project replaces the expired lease after 420 seconds. There are **no temporary projects to recover or delete**. Metadata cleanup failure can cause an error/temporary busy response, never deletion of source data.

## Presentation example and limitations

[examples/](examples/) provides a shared schema and two layouts; `multidesign_demo` creates both with synthetic content. Source and presentation include editable `slide_summary` fields and `include_in_presentation` on findings. The presentation uses 320 × 180 mm (16:9), explicit slide breaks, summary/severity totals, and short finding summaries. Keep these field IDs/types aligned when extending either design; change HTML/CSS freely. Extra technical source fields are supported.

Write concise summaries (roughly 3–5 short bullets or 50–80 words), short titles, and inspect every page. Excess content flows onto extra pages; nothing is silently clipped or automatically shrunk. Arbitrary content cannot be guaranteed to fit a slide. No automatic summarization, editable PowerPoint/PPTX, batch jobs, saved PDF history, percentage progress, or live collaborative unsaved editor state is included.

Rendering uses upstream Celery/eager execution and cancellation. Default upstream rendering timeout is 300 seconds; the plugin adds an outer cap of 360 seconds (or configured upstream limit + 5 when smaller). Collection is synchronous and file reads are not interruptible; configure storage connection/read timeouts. Snapshot limits are 16 MiB formatted JSON and 64 MiB raw assets/images. Base64/PDF copies consume additional memory. Set proxy timeouts above the render budget. Multi-minute/near-limit stress testing and a distributed Celery worker run remain unverified.

## Verification and upgrades

See [docs/VERIFICATION.md](docs/VERIFICATION.md) for actual commands/results and the distinction between mocks, real PostgreSQL/rendering, and browser/deployment checks. Synthetic generated PDFs are placed in ignored `artifacts/` by the rendering test.

On upgrade, review `adapter.py` against upstream permissions, field serialization, rendering signatures/resource handling and task cancellation. Review base-layer/PDF-viewer changes, regenerate lockfiles deliberately, run migrations/checks/tests, and perform the acceptance walkthrough before changing the source pin. Keep the plugin UUID unchanged. Removing the plugin from `ENABLED_PLUGINS` disables it; its small tables remain for re-enablement. Do not uninstall its migrations/tables without a backup.
