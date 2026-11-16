# Architecture and invariants

## Direct render instead of temporary copies

`render_pdf(project, project_type=alternate)` already exists in the inspected server. We use the same `format_project_template_data(project, project_type=alternate)` transformation, explicitly collect selected-design assets and referenced source images, then dispatch through `_render_pdf_task_async`. This adds snapshot isolation while keeping upstream Chromium/Vue → WeasyPrint and Celery/eager cancellation/timeout behavior. No source model save, conversion, project duplication, design customization, or read-only toggle occurs.

The worker receives a self-contained request containing the selected design's template, styles, formatted data and binary resources encoded as base64. Upstream task code enforces resource URL restrictions and returns renderer diagnostics/timings. Design/field location metadata from upstream is preserved when supplied. The plugin does not persist report bodies, PDFs, credentials or error logs of its own. Debug/worker logging and task result retention are controlled by upstream/server operators.

## Integration boundary

Only `PluginConfig` is a stable backend plugin export. The actual integration deliberately uses internal `sysreptor.pentests` models, permissions and render entry points, `Permission.PROJECT_UPDATE_SETTINGS`, and `ViewSetAsync`. Those symbols were inspected at the recorded commit; the code is not advertised as portable to older releases. `adapter.py` contains the data/permission/render services; `views.py` uses the standard async view helper. Migration depends on `pentests.0072_blindtrigramtoken_token_project_idx`.

Project permissions use both `only_permitted(user)` and explicit upstream permission predicates; design selection uses `ProjectType.objects.only_permitted(user)` plus the design read predicate, matching `ProjectTypeRelatedField`. Authentication is session-only; upstream default authenticated permissions and request throttles remain enabled. JSON parsers avoid accepting browser form submissions; no CSRF exemption or CORS exception is added. Save permissions are stricter than render permissions because saving changes plugin-owned project settings. Renderer results are withheld if membership, design visibility, active-user status or effective role permissions are revoked before completion.

## Snapshot contract

1. Authenticate and resolve accessible source/design; acquire a token lease in a short transaction.
2. Start a separate repeatable-read/read-only transaction. Recheck access, load target/source schemas, validate, format data, read resource bytes. Store a capture timestamp near the first read.
3. Commit the read transaction. Render entirely from captured values. Never query live report data during the task.
4. Recheck current access and return PDF/diagnostics or an error. Release only the matching lease token in `finally`, shielded from cancellation.

Concurrent requests never share mutable snapshot dictionaries. Same user/project duplicates are rejected while other users or projects can render independently. A project row lock is held only for lease acquisition. Lease rows contain no design/report data. Their expiry is bounded, scoped to source and user; takeover replaces only the matching row. No recovery path calls project deletion.

Database isolation is consistent across all model reads; external blob storage is not an MVCC participant. Snapshot collection may fail if an asset is removed before it is read. Once bytes are captured, later asset/content edits do not affect the render. Saved collaborative edits committed after the first read appear on the next generation. Unsaved browser text is never included. Default upstream database settings (no request-wide `ATOMIC_REQUESTS`) are required.

## Validation subset

Comparison is structural and conservative, independent of current report values. Every field used by the target must exist in the source with the same type. Lists recursively compare item types and objects compare properties by ID. All source enum values must be accepted by the target, including nested enums; labels can differ. JSON schema, string regex, numeric bounds and CVSS version must match. Unknown future field types fail closed. Target-only optional fields are rejected so users must first add them to the editing/source design. Extra source fields and nested properties are allowed. Required/default values do not trigger conversion; upstream formats defaults as usual.

The validator does not analyze arbitrary Vue expressions or infer undeclared fields accessed by HTML, validate data completeness, summarize content, or guarantee page fitting. A design author must align its declared schema and template. Rendering warnings remain visible to the user.

## Failure behavior

Validation and inaccessible IDs fail before dispatch. Storage/resource-limit failures leave the source untouched and release the lease. Upstream PDF errors return messages with HTTP 422, timeouts and task/storage failures show retry guidance. A broken or cancelled render has no project-copy cleanup obligation. If database cleanup fails, the expiring lease may temporarily block the same user's next action; crash recovery never broadens access. Browser disconnection may cancel the HTTP render; upstream attempts to revoke its Celery task. Synchronous storage reads can finish after cancellation, so the lease cleanup waits behind that work. Do not treat a disconnect as proof that a remote task was terminated.
