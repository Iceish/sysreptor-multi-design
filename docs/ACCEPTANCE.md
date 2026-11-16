# Manual acceptance walkthrough

Use only the isolated local Compose stack and synthetic data. Automated rendering and browser smoke checks have produced both PDFs, exercised the real menu/viewer/downloads, and verified error/retry UI. This longer manual walkthrough, especially overflow, permissions and worker interruption, should still be performed before deployment.

1. Run the README development setup, create local user `demo`, then `./scripts/dev.sh demo --username demo`. Sign in at http://127.0.0.1:8800.
2. Open **SYNTHETIC Multi-Design Demo**. Record the source design, report/finding values, project images/attachments and read-only state. There should be two synthetic findings.
3. Open **Outputs**, choose **Technical report**, and click **Generate PDF**. Check progress, three A4 portrait pages, summary and detailed findings. Change the filename to `exampleco-technical.pdf` and download. Open the downloaded PDF.
4. Choose **Presentation**. The old preview must clear. Generate again. Expect three landscape 16:9 pages: executive overview with severity count, then two short finding slides. Download as `exampleco-presentation.pdf`. It is a PDF, not a PPTX.
5. Return to the original project editor. Its design, sections, findings, images, attachments and read-only state must match step 2. No second editable project should exist.
6. Edit one finding's `slide_summary` in the source project and save. Generate the presentation again: the new text must appear. A previously downloaded PDF stays unchanged.
7. Uncheck `include_in_presentation` for one finding, save and regenerate. That finding's slide is absent; total severity counts still describe the whole report. Restore it.
8. Put more than a slide's worth of text into a summary. Verify visible overflow becomes extra pages, not hidden clipping; shorten it and regenerate. Check all page boundaries visually.
9. Create a copy of the presentation design in the UI and add a target-only `new_summary` markdown field. Select it in Outputs: compatibility diagnostics must name the field and generation must be disabled. A direct POST with that design ID must also fail. Add the field to the source schema or remove it from the target, reload Outputs and retry.
10. Put `![missing](/images/name/nonexistent.png)` in a source markdown field used by the technical report. Generate: the missing-resource warning must be visible. Remove the reference and retry. A renderer failure with no PDF should show messages and a retry button.
11. Double-click **Generate PDF**: the UI disables duplicate submission. Submit a second request in another tab while the first runs: expect HTTP 409 for that same user/project. A second authorized member can render independently.
12. Try an unrelated user and a private design owned by another user: no project or design access through API URL guessing. Mark the source read-only: preview/download still work as in upstream, but output settings cannot be saved. Check saving also fails for a member without project settings permission.
13. Optionally stop the rendering worker or lower `PDF_RENDERING_TIME_LIMIT` in the local stack, trigger generation and verify timeout/retry guidance. Restart and retry. Do not change a production worker for this test.

Automated tests cover source preservation, scoped lease recovery, failure cleanup, real PDF sizes/page counts, missing-image diagnostics, and database isolation. They do not replace visually inspecting long real-world layouts, session navigation, download handling, proxy timeouts, or distributed worker cancellation in your installation.
