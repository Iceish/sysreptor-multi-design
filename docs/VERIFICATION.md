# Verification record

Run date: 2026-11-15. Only synthetic data was used. No remote repository, publication, push, or live-server deployment was performed.

## Actual local checks

- Inspected all six requested official sources, cloned SysReptor/plugin-example/reptor into task-local temporary directories, and recorded exact commits in `upstream.env`/`PLAN.md`. The reptor context-manager behavior was verified in source.
- `bash -n scripts/dev.sh scripts/fetch-upstream.sh`: passed.
- `scripts/dev.sh init`: generated ignored mode-0600 local secrets, fetched and checked out the pinned upstream commit; no core changes.
- `docker build --build-arg VERSION=mdo-6b0b1fcf7cae6f9e8d308dfda0516dab7a0cd787 -t multidesign-upstream:6b0b1fcf sysreptor-src`: passed, including upstream frontend, PDF viewer, rendering bundle, core plugins, static collection and license build check.
- `docker compose --env-file .env.dev build app`: passed; plugin Nuxt assets are bundled in the final image.
- `scripts/dev.sh check`: passed in the packaged image: Django system check found no issues; `makemigrations --check --dry-run` found no changes.
- `scripts/dev.sh test`: **29 passed**, against PostgreSQL 17 and the exact pinned upstream source image. Final run: 29 passed in 22.02 seconds, with the pytest cache provider disabled for the read-only image tree.
- `ruff check --no-cache /custom_plugins/multidesign`: passed using the plugin's focused `ruff.toml` (syntax, undefined/unused names and import ordering).
- `(cd sysreptor-src/packages && npm ci)` and plugin `npm ci`, `npm run typecheck`, `npm run generate`: passed with Node 24.22.1. Type checking includes inherited base-layer code. Build warns about the inherited Vuetify/font bundle size.
- `scripts/dev.sh up`: passed; the isolated local server and health check ran on loopback port 8800.
- `scripts/dev.sh smoke`: passed against the packaged Community edition using a local synthetic superuser and real session login. Playwright clicked the registered Outputs menu, selected both saved outputs, generated and downloaded two real PDFs, edited the technical filename, confirmed the old preview cleared on design change, and verified that the official PDF viewer rendered a canvas. A deliberately intercepted HTTP 503 exercised visible failure/retry; retry used the real backend. No browser JavaScript errors were reported. The screenshot is `artifacts/outputs-browser.png`; downloaded files are `browser-technical.pdf` and `browser-presentation.pdf`.
- The real rendering test produced `artifacts/technical-report.pdf` and `artifacts/presentation.pdf`, validated them using pikepdf, and confirmed three portrait pages versus three 16:9 pages. Cover-page raster previews were also inspected.

In this restricted workspace, Docker builds used `DOCKER_CONFIG=/tmp/mdo-docker-config` to place builder bookkeeping in a writable task-owned directory. Normal hosts do not need this override.

## What the tests actually exercise

Eleven schema unit cases cover extra source fields, missing optional targets, incompatible scalar types, nested list/object enum mismatches, JSON/CVSS/number/string constraints, and unknown types.

Eighteen PostgreSQL/backend cases cover anonymous/nonmember denial, private-design visibility on read/save/render, saved configuration/filename validation, upstream session/CSRF behavior, read-only permissions, rejection before dispatch, unchanged source rows/files/readonly/design, snapshot resources, later source edits, selected asset identity, resource caps, access revocation, lease takeover/ownership, and overlapping requests from different members. Rendering success, storage/snapshot failure, task failure, timeout, cancellation and no-PDF paths all release their own lease.

Actual Chromium/Vue → WeasyPrint rendering runs for both demo layouts and a missing-image warning. Access/schema/database checks use real upstream models/services and PostgreSQL. Failure injection and the concurrency barrier use mocked renderer calls to deterministically exercise orchestration, not real multi-worker process failures. Test settings enable eager rendering and disable license enforcement, as upstream's own tests do.

The preliminary `compose.validation.yaml` harness also passed 29 tests. It overlays exact current backend source on the official `2026.97` runtime plus Taskiq dependencies. This preliminary hybrid is clearly labeled and is not the production image. The later full-source image/check/test run removes that dependency mismatch. The validation harness has no exposed ports and its database uses ephemeral tmpfs. Both task-owned Compose stacks were stopped after verification. The development volumes (synthetic data only), ignored local secrets, built images, and generated artifacts remain for resuming locally.

## Dependency checks

The plugin npm dependency audit reported **6 low and 4 moderate** advisories (no high/critical), involving Nuxt/Nitro and build/archive/glob dependencies. The broader upstream workspace installation reported 58 advisories including 9 high and 1 critical in its full dependency tree. Dependencies remain pinned to inspected upstream/lockfiles; no forced dependency upgrades or core edits were made. Review upstream fixes and deliberately regenerate/test locks before changing the supported pin.

Browser checks caught and resolved an inherited Nuxt source-directory issue and a Vue component-name collision; successful builds alone were insufficient. Final frontend type checking and generation include the actual project page and shared PDF component.

## Integration limits

Distributed Celery execution/revocation, actual worker crashes during rendering, external object storage races, reverse-proxy disconnect/timeouts, near-cap/multi-minute reports, multi-process capacity/load, and every permission configuration/custom role have not been integration tested. Limits and timeout error paths were tested with synthetic/fault-injected cases; this is not a stress benchmark. Long slide text still requires visual layout review. Full manual acceptance steps are in `ACCEPTANCE.md`.
