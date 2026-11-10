# Visualization Engine Rebuild

## Decision

Replace the current heuristic-plus-flat-texture preview path with a staged, measurable room-visualization pipeline. Keep the existing tenant, project, product-catalog, upload, and authentication domains. Do not present the current renderer as photorealistic or the current heuristic detector as AI.

The first release remains self-hosted and local-inference-first. No room photo may be sent to a third-party inference API.

## Current-state findings

- When no compatible segmentation checkpoint is configured, `surface_detection.py` falls back to OpenCV GrabCut with fixed positional priors. This can select cabinets, shelves, or arbitrary image regions.
- The fallback confidence is a heuristic score, not a calibrated probability. The UI must not label it as an AI confidence score.
- The current Transformers adapter requires a checkpoint whose label map explicitly contains floor and wall classes. The repository does not bundle a commercially cleared checkpoint.
- SAM 2 can refine prompted object boundaries; it does not identify room surfaces or infer room geometry.
- The browser renderer repeats a texture in a pattern canvas and projects it through a coarse quadrilateral. It does not yet model real camera geometry, material BRDF, shadows, or reflections.
- The uploaded screenshot is a hard negative case: a close-up of cabinets and tiled shelving with no clear continuous room floor. Automatic detection must abstain rather than return a confident, incorrect polygon.

## Target pipeline

1. **Input validation and scene triage**
   - Classify the photo as suitable, ambiguous, or unsuitable for the requested surface.
   - Return explicit reasons and request a wider/clearer photo or manual selection when the target is not visible.
   - Never fabricate a surface polygon to satisfy an API response.

2. **Semantic scene understanding**
   - Run a locally hosted, commercially cleared indoor-scene model.
   - Produce per-pixel labels/probabilities for floor, wall, ceiling, furniture, cabinetry, shelving, rugs, fixtures, doors, windows, and people.
   - Keep model adapter, weights, label map, model version, and license metadata explicit.
   - If the configured model is missing, incompatible, or unapproved, mark AI detection unavailable; do not silently market GrabCut as AI.

3. **Surface proposal and interactive correction**
   - Produce candidate masks, not just one forced polygon.
   - Score candidates using semantic probability, connectedness, boundary evidence, and geometric plausibility.
   - Include calibrated confidence and an abstain threshold.
   - Support click-positive, click-negative, brush add/erase, polygon vertex editing, undo/redo, zoom, and reset.
   - Persist user-confirmed masks and provenance separately from model proposals.

4. **Geometry and material mapping**
   - Estimate the surface plane and vanishing geometry from user-confirmed boundary plus image evidence.
   - Use a homography for planar surfaces; do not claim metric dimensions when only a single uncalibrated photo is available.
   - Derive tile scale from declared product dimensions and user calibration (known edge/dimension) where possible.
   - Support straight stack, brick, diagonal, and user-defined layout with physically consistent grout width.
   - Reject degenerate quadrilaterals and warn when perspective cannot be estimated reliably.

5. **Photographic compositing**
   - Preserve source-image illumination, low-frequency shading, shadows, highlights, and reflections.
   - Keep foreground objects in front of the replacement material using instance/object masks and edge refinement.
   - Avoid a uniform opacity wash; material appearance should be controlled by calibrated roughness/finish and lighting decomposition.
   - Maintain a non-destructive render stack so material, grout, mask, and geometry can be edited independently.

6. **Quality and observability**
   - Store model/provider version, inference device, timings, selected surface, confidence, and warnings with each analysis.
   - Provide deterministic test fixtures and a held-out real-room photo evaluation set with rights-cleared images.
   - Report floor/wall IoU, boundary F-score, occlusion recall, and manual-correction time.
   - Benchmark GPU and CPU paths on the self-hosted deployment target.

## UI requirements

- Replace the current unhelpful boundary point display with a dedicated mask-editing mode.
- Make the selected surface visible with a translucent mask and high-contrast editable handles.
- Provide distinct states: Detecting, Needs selection, Ready to render, Low confidence, and Detection unavailable.
- Do not show a numeric confidence percentage unless it is calibrated and validated.
- Keep the original photo and rendered result available for before/after comparison.
- Provide clear controls for tile size, grout width/color, orientation, offset, and finish.

## Delivery sequence

### Phase A — Honest detection and correction
- Separate heuristic fallback from AI detection in API metadata and UI.
- Add an abstention/ambiguous result contract.
- Add candidate-mask and user-confirmed-mask API contracts.
- Implement reliable manual mask editing and persistence.
- Add tests for cabinets/shelves close-ups, rugs, furniture occlusion, low light, reflective floors, and portrait photos.

### Phase B — Local semantic and instance segmentation
- Select a commercially cleared checkpoint and document the rights chain for architecture, weights, and training data.
- Add indoor semantic segmentation and object/instance segmentation adapters.
- Validate on a rights-cleared held-out dataset before enabling the provider by default.
- Add optional prompt-based mask refinement only after semantic proposals are correct.

### Phase C — Perspective-aware material renderer
- Replace the repeated flat grid with planar projective mapping and physically consistent tile dimensions.
- Add grout and layout controls.
- Add lighting/shadow preservation and foreground compositing.
- Add image regression tests with reference outputs and perceptual review.

### Phase D — Product quality gate
- Run blind evaluation on diverse phone photos and room types.
- Do not call the renderer photorealistic or production-ready until the metrics and human review gate pass.
- Preserve local-only inference and self-hosted deployment.

## Acceptance test: uploaded cabinet/shelving photo

For a close-up showing wooden cabinets and tiled shelving but no clearly visible continuous floor:

- Floor detection must return `needs_manual_selection` or `not_visible`, not a floor polygon cutting through cabinetry.
- Wall detection must not select cabinet faces or shelving as a wall.
- Confidence must not be a fabricated heuristic percentage.
- No material is applied until the user confirms a valid surface mask.
- If the user manually selects a planar tiled panel, mapping must follow its perspective and respect the selected boundary.

## Non-goals for the first rebuild increment

- Do not promise Roomvo parity from a generic pretrained model.
- Do not bundle ADE20K-derived weights without explicit commercial rights.
- Do not treat relative monocular depth as metric geometry.
- Do not use SAM 2 as a substitute for semantic room understanding.
