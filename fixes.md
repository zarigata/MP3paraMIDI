# Current Issues and Recommended Fixes

## 1. Web UI Rendering and Layout Problems
- **Symptoms:** Stem cards render partially off-screen and require manual scrolling; user perception is that some stems are missing or hidden.
- **Cause:** The results section (`#resultsSection`) is initially rendered with `hidden` attribute and revealed only after separation. The layout uses a fixed grid that may overflow the viewport when multiple stems are present.
- **Fixes:**
  - Ensure the results section scrolls into view automatically after rendering stems (e.g., `resultsSection.scrollIntoView({ behavior: 'smooth' })`).
  - Adjust CSS grid/list layout to wrap vertically or provide pagination for large numbers of stems.
  - Add explicit status text for the number of stems detected.

## 2. Gradio Interface Not Mounting in Runtime
- **Symptoms:** Front-end lacks the Gradio tabs that should expose additional functionality; UI only shows the custom Flask page.
- **Cause:** The unified FastAPI mount at `/gradio` depends on Gradio 5, but the static SPA never links to that path. Users expect the Gradio experience but only receive the custom UI.
- **Fixes:**
  - Provide navigation to `/gradio` or embed the Gradio app in the main page.
  - Alternatively, migrate the missing functionality from Gradio into the custom UI, keeping feature parity.

## 3. MIDI Conversion API Usage
- **Symptoms:** Direct `curl` calls to `/api/convert-to-midi` without the JSON wrapper return `400 Invalid or missing JSON body`.
- **Cause:** The endpoint strictly requires a JSON body with `job_id` and optional `stem_names`. Front-end handles this correctly, but manual testing using `curl` failed due to missing payload structure.
- **Fixes:**
  - Document the exact request format (e.g., `{"job_id":"<uuid>","stem_names":[]}`) in README/DOCKER.md.
  - Optionally relax the API to accept form-encoded requests for easier manual testing.

## 4. Stem Count Expectations ("Voices")
- **Symptoms:** Users expect per-instrument or per-vocal isolations beyond the 4 default Demucs stems.
- **Cause:** Demucs `htdemucs` model outputs `drums`, `bass`, `other`, and `vocals`. UI labels them as "voices", causing confusion.
- **Fixes:**
  - Clarify messaging: rename "voices" to "stems" and explain the Demucs stem set.
  - If more granular separation is required, integrate alternative models (e.g., MDX-net) and update back-end to expose additional stems dynamically.

## 5. UI Responsiveness and Typography
- **Symptoms:** Large headings and cards overflow on smaller viewports; buttons may wrap awkwardly.
- **Cause:** CSS uses fixed clamp sizes for typography and card dimensions; grid lacks media queries below ~768px.
- **Fixes:**
  - Add responsive breakpoints to `styles.css` for mobile/tablet.
  - Test layout via browser dev tools and adjust padding/margins accordingly.

## 6. MIDI Output Completeness
- **Symptoms:** MIDI conversion may appear to miss certain melodic lines.
- **Cause:** Melodia plugin applied only to `vocals`; other stems rely on Basic Pitch, which can miss polyphonic nuances. Missing plugin detection in runtime previously prevented Melodia usage.
- **Fixes:**
  - Verify runtime has `VAMP_PATH` and `mtg-melodia` plugin (recent Docker changes address this).
  - Consider exposing per-stem conversion options so users can re-run specific stems with alternative models.

## 7. Testing & Logging Gaps
- **Symptoms:** Hard to diagnose front-end state since console output only logs initialization.
- **Cause:** `main.js` lacks logging for request lifecycle and error handling beyond `showStatus`.
- **Fixes:**
  - Add structured logging (console and/or server-side) for API requests, errors, and state transitions.
  - Include integration tests covering `/api/separate` and `/api/convert-to-midi` flows.

---

### Immediate Priorities
1. **UI Experience:** Auto-scroll and responsive design to prevent stem cards from feeling hidden.
2. **User Guidance:** Clarify stem terminology and provide documentation on API usage.
3. **Feature Surfacing:** Decide whether to expose `/gradio` or consolidate functionality in the custom UI.
