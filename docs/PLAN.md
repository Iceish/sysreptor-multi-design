# Implementation plan

1. Inspect and pin official sources; isolate internal APIs in an adapter.
2. Render a read snapshot directly with the selected design using upstream rendering machinery. Never create or mutate a project.
3. Add project-owned output preferences, session/CSRF endpoints, server-side access checks, conservative recursive schema validation, and expiring render leases.
4. Add an Outputs project menu and Nuxt plugin page using the official base layer and PDF component.
5. Supply compatible portrait/16:9 synthetic examples, pinned Docker development setup, focused tests, and an acceptance walkthrough.
6. Run available frontend, Python, and local integration checks; record evidence and unverified checks.

## Sources inspected (2026-11-15)

- SysReptor main: `6b0b1fcf7cae6f9e8d308dfda0516dab7a0cd787` (2026-11-13).
- Plugin example: `e3edc38b5e9f050101d2faf709d1a9fe9036b2a1`.
- reptor main: `e1911a533506dec46226986ab5e4ff660b285718`.
- https://docs.sysreptor.com/setup/plugins
- https://docs.sysreptor.com/cli/projects-and-templates/project
- https://docs.sysreptor.com/designer/designer

The CLI still duplicates, force-switches design, renders, and deletes; its context manager still has no try/finally. The server already accepts `project_type` in `render_pdf` and `format_project_template_data`. Designs contain schemas and assets, so replacing HTML alone is insufficient. The adapter freezes formatted content and resources, then uses upstream `_render_pdf_task_async` to retain Celery/eager execution, cancellation and rendering limits. These are internal, version-sensitive APIs, not stable exports of `sysreptor.plugins`. No temporary-copy recovery is needed because no copies exist.
