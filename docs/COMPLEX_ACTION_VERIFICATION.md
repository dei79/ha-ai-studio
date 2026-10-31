# Complex Action verification — 2026-10-31

## Changed files

Studio: `app/assets.py`, `actions.py`, `plugins.py`, `plugin_runner.py`, `server.py`; frontend `ActionEditor.tsx`, `SchemaEditor.tsx`, `lib/types.ts`; tests `test_assets.py`, `action_editor_fixture.py`; documentation `ARCHITECTURE.md`, `COMPLEX_ACTIONS.md`, this report.

Sibling Actions repository: `editor/package.json`, lockfile, TypeScript configuration, Vite configuration, `editor/src/editor.ts`, `types.ts`, `editor.scss`; generated Action `ui/editor.js` and `editor.css`; manifest, runtime `action.py`, `engine.py`, `correction.py`, hashed dependency lock, bundled models/provenance, unit tests, README, license and attribution files. No private fixtures are included in either repository.

## Results

- `./scripts/test.sh`: 106 tests passed, one release test skipped in the container without repository metadata.
- Host `python3 -m unittest discover -s tests -p test_release.py -v`: four tests passed, covering release metadata separately.
- `./scripts/test-mqtt.sh`: both isolated real MQTT suites passed (A/B/C routing and discovery lifecycle).
- Studio frontend build: TypeScript/Vite and 19 frontend tests passed.
- Action `npm run build`: strict TypeScript check, Vite bundle and SCSS compilation passed.
- Action Python suite in Linux amd64 with pinned dependencies: six tests passed, including actual LiteRT invocation.
- `git diff --check`: passed.
- IAB on a separate temporary fixture with no MQTT lifecycle: Ingress module/style loading, private image upload, real preview, drawing/moving/resizing/removing regions, text editing, save/reload persistence, reference replacement/Undo, desktop 1280px and tablet 768px layouts checked.
- Three independent reviews completed; reported HIGH issues fixed and backend/UI fixes reviewed again without remaining HIGH findings.

## Limits

Synthetic fixtures establish integration and correction behavior, not accuracy on real meters. Recognition accuracy and transition behavior need representative user meter images. Arbitrary gauge scales, other historical upstream models and ESP32 hardware services are outside this adaptation. Live HA authentication and production TLS were not exercised. UI tests used only synthetic private temporary storage and did not publish MQTT. Existing real active instances were not reloaded or reconfigured; deactivate and reload from source to adopt the new Action build.

## Crop follow-up

The Action now persists a rotated-image crop, translates ROI coordinates for inference and rejects reading regions that touch unsupported pixels after alignment. Zoom buttons and wheel zoom are replaced by crop drawing, exact crop coordinates, Reset crop and Fit area. Existing regions must remain inside the crop.

TypeScript/SCSS build and nine Action tests pass, including actual cropped preview dimensions, pixel equivalence, rotation, invalid bounds and missing pixels at all four image edges. Backend and UI source reviews completed. This follow-up was not interactively checked: the user's existing IAB tab contains unsaved configuration, which was preserved. Save those changes and reload the inactive Action from source before using the new editor.

## Crop handles follow-up

`editor/src/crop.ts` supplies hit testing and bounded corner/edge/move geometry; `editor.ts` renders eight Word-style grips immediately when crop mode opens. Changes remain candidates until Apply/Enter; Cancel/Escape restore the applied area. Pending crop changes block saving and recognition until resolved. The Action package includes the rebuilt module. README and editor package test command were updated.

TypeScript/SCSS build and three geometry tests passed. IAB under the isolated Ingress fixture verified immediate frame visibility, both corner drags, an edge drag, movement, Apply, saving/reload persistence and Cancel restoring the previous height. No MQTT was published. UI source review found no HIGH issues. Screenshot: `/tmp/meter-crop-handles.png` (synthetic image only).

## Move view center guides

Renamed Pan to Move view in the TypeScript editor. Guides are drawn in viewport coordinates on each centered axis; dragging snaps within six CSS pixels to the visible image/crop center. Drag displacement is measured from the original pointer position so small movements can escape snapping. This changes only the view, not image or ROI coordinates. TypeScript/SCSS build and existing editor tests passed. Interactive checking was deferred because the current user tab contains unsaved edits; those were preserved.

## Icon toolbar follow-up

Updated Action `editor/src/editor.ts` and `editor.scss`, and rebuilt generated JS/CSS. The first row contains pointer, four-direction move and crop SVG buttons in that order, with hover/keyboard-focus tooltips, accessible labels and active states. Other operations remain text buttons in a separate row below. Strict TypeScript and SCSS/Vite build passed. The user tab had unsaved edits and was left unchanged; visual verification of this revision remains pending.

## Unified frame interaction

Updated Action TypeScript editor/types, SCSS, generated JS/CSS, manifest, engine, tests and README. Select / move draws unassigned frames on empty space, moves existing frames by their interiors and resizes them at all four corners. Tiny drags/clicks do not create frames. Frame types are selected in the new Frames & types list below the image; old type-specific drawing tools are removed. Runtime rejects unassigned frames before inference. Type assignment selects a free position excluding the frame itself.

Strict TypeScript/SCSS build, three geometry tests and ten Python tests passed. This revision has not been interactively verified in IAB; the existing user draft was not changed.

## Value pill builder

Updated Action `editor/src/editor.ts`, `types.ts`, `editor.scss`, generated JS/CSS, manifest, engine, Python tests and README. Meters & values now offers frame pills and one decimal-comma pill; users add/select/remove/reorder frames instead of setting numeric positions and decimal shift. Comma keyboard input is supported after frame selectors and at the add selector, with a comma button alternative. Reading checks are collapsed separately. Type/geometry editing stays in the frame controls.

The runtime resolves explicit layouts without mutating settings, preserves legacy configurations, validates frame ownership/order/types, ignores unused frames in explicit layouts, and derives decimal shift. Mechanical digits must precede analog dials for the existing transition-correction algorithm. Each frame belongs to at most one value.

TypeScript/SCSS build, 12 Python tests and three editor geometry tests passed. Tests cover comma positions, no-comma integer values, invalid sequences, ownership and legacy preservation. Backend/UI reviews found no HIGH findings; rejected dropdown selections now restore their saved display. Interactive verification of this revision remains pending.

## Printed number blocks

Added `number_block.py`, engine/layout integration, manifest region fields, TypeScript types/editor controls and generated editor assets in the sibling Action repository. Added `tests/test_number_block.py`, usage notes and attribution. Studio's Dockerfile now installs Tesseract plus English trained data; `ha_ai_studio/THIRD_PARTY.md` documents the runtime dependency.

Number blocks use the earlier local App's two-threshold single-line digit OCR, with configurable length and comparison checks instead of fixed coordinates/private identity. They occupy one complete value and return strings preserving leading zeros. They cannot be mixed with numeric digit/dial pills or numeric plausibility checks. OCR errors produce per-value unreadable results. Image enlargement and the shared OCR deadline are bounded.

Verification: 21 Action Python tests pass in the Linux amd64 runtime, including real Tesseract on synthetic numbers and the full crop/alignment/preview path. Three editor geometry tests and the TypeScript/SCSS build pass. Backend, UI and test-strategy reviews completed without HIGH findings. Rejected optional OCR input is restored to its stored value. Actual optical accuracy still depends on the source image.

Interactive testing of this revision was deferred: IAB shows unsaved user changes on the current Action. Those edits were preserved; its bound snapshot was not reloaded. Save the user draft, then reload the inactive Action from source to adopt the new editor. No live HA App or production configuration was changed.

Studio verification for the number-block change: `./scripts/test.sh --skip-build` passed 106 tests (one release-metadata check skipped in the container); the four host release checks passed separately. `./scripts/test-mqtt.sh` passed both isolated MQTT suites, and all 19 Studio frontend tests passed. Local Studio was rebuilt and started with `docker compose up -d --build`.

## Optional recognition quality checks

Action changes: `engine.py` adds original/±2-pixel digit/dial inference, per-type fit thresholds, optional color/grayscale autocontrast, comparison of corrected meter values across shifts, and per-region rejection reasons. Samples must remain inside valid aligned pixels. The shared recognition budget is 20 seconds. `run` supports an optional distinct `confirmation_image`; required confirmation cannot pass a reference-only preview. A numeric value or number-block string must agree exactly between captures. `rate_tolerance` adds an optional fixed allowance to the maximum-rate check. Existing settings preserve their prior behavior until options are enabled.

Updated the Action manifest, TypeScript editor/types, SCSS, generated UI assets and README; added `tests/test_quality.py`. Preview marks rejected frames in red with textual reasons. Advanced controls synchronize after Undo, invalid new numeric options restore stored values, and confirmation diagnostics preserve existing rejection reasons. No Studio runtime code changes were needed for these checks.

31 Action tests pass in the locked Linux amd64 runtime, including actual model/OCR paths, stability after correction, alignment padding, preserved leading zeros, two-capture agreement/rejection, duplicate-image rejection, preview/network isolation, shared deadline and rate tolerance. TypeScript/SCSS build and three editor geometry tests pass. Three read-only backend/UI/test reviews found no HIGH issues. Local Compose was rebuilt and started.

IAB still shows unsaved changes in the user's current Action, so interactive testing and reloading that instance were deferred to preserve them. Save and reload the inactive Action from source, then enable the desired quality checks under Alignment, recognition and image source. Multi-capture acquisition remains an HA responsibility; no HA automation or live App was changed. Exact agreement may reject legitimate readings of moving meters and needs representative-image validation.

Follow-up verification: Studio's `./scripts/test.sh --skip-build` passed 106 tests (one container release-metadata skip; all four host release tests passed). Both `./scripts/test-mqtt.sh` suites passed against isolated brokers. The Action's three JSON schemas and an example using all new settings validated successfully. No live broker publication was performed by UI testing.

## Reference-line straightening

Updated Action `editor/src/editor.ts`, `types.ts`, generated JS/CSS, manifest and `engine.py`; added `editor/src/straighten.ts`, `editor/tests/straighten.test.mjs`, and `tests/test_straighten.py`. The new Straighten image tool is beside Rotate 90° in the Image rotation toolbar group. Dragging a line applies its minimal horizontal correction on release. The inspector shows the saved correction and Reset; Escape cancels and Undo restores exact previous settings. Existing ROI/crop rectangles are transformed to enclosing bounds, with out-of-image changes rejected. The fixed canvas is clipped in Crop mode as well.

The stored `straighten_angle` is applied after quarter turns and before crop/alignment to reference, request and confirmation images. Validity masks prevent reference regions, matched alignment anchors and aligned reading/stability samples from using empty rotated corners. Original assets are unchanged.

35 Action Python tests and five editor geometry tests passed, including horizontal-line geometry, reverse drawing direction, model/OCR regressions, quarter-turn + straightening + crop pixel output, and padded anchor/ROI rejection. TypeScript/SCSS build passed. Three read-only reviews completed with no HIGH findings. Local Compose was rebuilt. IAB confirmed the new toolbar control and inspector in the user's open editor; drag/reset/Undo interactions were not exercised on the user's configured image. Exact optical performance and enclosing rectangle fit still require image-specific validation.

Straightening regression checks: `./scripts/test.sh --skip-build` passed 106 tests (one container release skip); four host release tests passed. Both isolated `./scripts/test-mqtt.sh` suites passed. No live HA or ESPHome changes were made.

## Reference image gallery

Updated the Action manifest with a bounded `references` image list while retaining the selected `reference` contract. Added `editor/src/references.ts` and `editor/tests/references.test.mjs`; updated editor/types/SCSS, generated assets and README. The old top file chooser is replaced by an Add reference image toolbar icon; two or more images show Previous/Next and a counter. Images share exactly one set of regions, meter layouts, crop, rotation and straightening. Same-size uploads and browsing preserve editor zoom/pan. Selecting an image marks the draft changed and clears stale recognition results. Saving makes that image the active runtime reference. Legacy single-image settings remain compatible.

Seven editor tests and the TypeScript/SCSS build passed. Three read-only reviews completed without HIGH findings. Review fixes guard Undo during uploads, prevent Fit from using empty-image dimensions, preserve load errors, and mark initial fit complete so later layout resize does not reset gallery zoom. Unit tests cover legacy migration, deduplication, image limits, dimensions and unchanged shared geometry. IAB inspection confirmed a saved inactive user Action still bound to its older snapshot; no reference uploads or saved user configuration were changed during checking. Full interactive upload/paging verification remains pending.

Gallery regression verification: 106 Studio tests passed (one container release skip), four host release tests passed, and both isolated MQTT suites passed. Local Studio was rebuilt with `docker compose up -d --build`.

## Version checkpoints: Studio v0.0.9 / Analog Meter Reader v0.2.0

Local Compose rebuilt successfully. Studio: 106 tests passed with one container release skip; all four release checks passed on the host. Both isolated MQTT suites passed. Action: 40 Python tests and eight editor tests passed; generated TypeScript/SCSS assets built successfully. Recent editor layout and toolbar changes have not received a complete interactive IAB regression pass. No live HA deployment or remote publication was performed.
