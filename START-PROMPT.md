Build a self-hosted SysReptor plugin called Multi-Design Outputs in this repository.

Objective
Allow users to write one pentest project and generate PDFs using multiple existing report designs from the web UI: for example, a classic portrait technical report and a landscape presentation PDF. Keep one source of report content. This is a SysReptor server/frontend plugin, not a Codex or ChatGPT plugin. Editable PowerPoint export is outside the initial scope.

First steps
Read repository instructions and inspect the current official sources before choosing APIs:
- https://docs.sysreptor.com/setup/plugins
- https://github.com/Syslifters/sysreptor-plugin-example
- https://github.com/Syslifters/sysreptor
- https://github.com/Syslifters/reptor
- https://docs.sysreptor.com/cli/projects-and-templates/project
- https://docs.sysreptor.com/designer/designer
Use a separate custom-plugin repository rather than modifying SysReptor core. Record the upstream version or commit you implement against. Write a concise implementation plan, then implement and verify the first usable version; do not stop at planning. Use reasonable defaults and ask only about blockers. Do not modify Plume or other sibling projects.

Known CLI behavior to verify
The reptor project --render --design DESIGN_UUID command duplicates the source project on the server, switches the duplicate to the selected design with force=True, renders its PDF, then deletes the duplicate and restores the client context. This is the user experience to expose in the web UI. The previously inspected reptor commit was e1911a533506dec46226986ab5e4ff660b285718; check the current implementation rather than assuming it is unchanged. Its duplicate_and_cleanup context manager lacked try/finally, which this plugin must improve upon. A design includes report/finding field definitions and assets as well as HTML/Vue/CSS.

Initial product behavior
1. Add an Outputs page to each project's menu using supported plugin hooks and the normal session authentication.
2. Offer the current project design and other existing designs the user is authorized to use. Support selecting a design, previewing its generated PDF, and downloading it with a sensible editable filename.
3. Remember a project's configured output choices if supported cleanly by plugin-owned models; users can label them Technical report and Presentation. Start with one output rendered per action; batch output is optional later.
4. Generate both outputs from the latest source project content without changing the source project's design, sections, findings, attachments, or read-only state. Do not maintain two independently edited projects.
5. Show progress, useful render warnings/errors, retry, and empty states. Prevent accidental duplicate submissions. Reuse the official plugin frontend conventions and PDF viewer if available.
6. Output is PDF. A slide template must intentionally render concise content; do not imply the plugin automatically summarizes a technical report or produces a .pptx.

Backend and data requirements
Prefer a supported server rendering API capable of applying an alternate design without mutating the source, if upstream provides a suitable one. Otherwise implement the temporary-copy workflow through supported server APIs/services. Document the choice. Do not shell out to reptor or require a stored user API token.
Enforce project membership/access and design visibility/use permissions on every endpoint; never rely solely on frontend filtering. Follow upstream CSRF, session authentication, and read-only permission rules. Do not broaden access for the feature.
Check field compatibility by IDs, types, nested structures, and relevant enum values. Surface meaningful mismatches before rendering. Use conservative validation for the MVP and document any supported subset. Do not blindly force incompatible conversions. Extra source fields unused by a layout are a normal use case. Preserve uploaded project images and selected design assets in the rendered result.
If using temporary projects, guarantee cleanup on success and handled errors with try/finally, isolate concurrent requests, and provide bounded, ownership-scoped recovery for stale plugin-created copies after a worker crash. Never delete an unrelated project. Use upstream transactions/task patterns appropriately; do not keep a database transaction open across a long PDF render unnecessarily. Avoid logging report bodies or credentials. Handle the possibility that source duplication, design selection, rendering, or cleanup fails.
Use the existing render/task machinery where possible. Verify appropriate timeouts and behavior for large reports, missing assets, and source edits during rendering. Document snapshot semantics.

Presentation example
Include synthetic demonstration data and two compatible example designs, or reproducible instructions to create/import them. Share field IDs/types, changing HTML/CSS/layout. The presentation example should use a 16:9 page ratio, explicit slide/page breaks, summary and severity information, and short finding summaries. Optional fields such as slide_summary and include_in_presentation must exist in the source design to be editable there. Explain how to keep schemas aligned and how long content overflow is handled.

Deliverables
- Installable plugin structure with Django backend and supported frontend integration.
- Reproducible Docker/self-hosted development setup based on the official plugin example, with no secrets committed.
- README with installation, enablement, supported SysReptor version/edition requirements, development commands, usage, data lifecycle, limitations, and upgrade notes.
- Focused tests for access control, field compatibility, unchanged source project, success/failure cleanup, and concurrent render isolation where applicable.
- Frontend build and backend checks actually run where the environment supports them. Distinguish mocked/unit checks from integration verification against a real SysReptor instance.
- A manual acceptance walkthrough showing one source project producing two different PDFs, plus an error path.

Work autonomously on local implementation and synthetic validation. Do not deploy to a live SysReptor instance, use real pentest data, create a remote repository, publish, or push without further user instruction. If a real server is unavailable, complete the local plugin and reproducible setup, and state exactly which integration checks remain unverified. Finish with what works, commands run, and remaining limitations.
