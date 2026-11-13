# 07 | Spatial UI and supplied media

## Asset inventory (do not request more)
User has supplied on their local machine three video roles and five image roles under `07_dashboard/assets/`. Inspect actual filenames, extensions, dimensions and decode support before integrating; screenshot shows image stems, not extensions. Do not rename/delete user files without permission. Use explicit build-time asset registry based on real files; no remote stock images or generated extra assets. Existing logo is Avoflare PNG per user request. Other images may be PNG/JPEG/WebP; resolve actual suffix. Videos are expected MP4; verify actual format.

| Role | Expected stem | Placement |
|---|---|---|
| Login cinematic video | login_hero | login right panel |
| Attached wearable video | watch_attached | patient monitoring device panel |
| Removed wearable video | watch_removed | same panel |
| Logo image | logo | shell, login, reports if appropriate |
| Female avatar | patient_avatar_female | profile when documented gender maps |
| Male avatar | patient_avatar_male | profile when documented gender maps |
| Attached wearable still | watch_attached | static fallback for attached video |
| Removed wearable still | watch_removed | static fallback for removed video |

If avatar gender unknown/unmapped, use plain patient ID or neutral initials CSS, not infer appearance. No need for recovery hero image, twin fallback image or more videos. Use simple procedural SVG fallback for twin. Keep logo proportions and avoid recoloring. If asset has pale mint backdrop, contain it in a white/sage neutral area without stretching or adding gradients. Verify actual image quality and video continuity; do not promise same device if clips differ.

## Media implementation
Use HTML video with muted, playsInline, loop for two idle watch clips and login if appropriate, poster from corresponding still, accessible text equivalent. No audio autoplay. Reserve aspect ratio, use object-fit contain for product view, white parent, no crop that hides clasp or hand. Login media right panel (not full background behind text); on mobile omit or use static logo if needed. Preload metadata by default; prioritize clinical data; lazy-load only visible route. Pause when hidden/offscreen and on route change. Reduced motion, autoplay rejection, decode errors or missing video use still; missing still use textual status and simple neutral placeholder. Optional user pause control. No additional transition videos. No crossfade; direct replacement or brief neutral positional transition if needed; preserve aspect ratio and avoid flicker by loading target before switching, but status text updates immediately. Never block safety on media readiness.

## Wearable state machine
Presentation state is independent of clinical decision; backend evidence drives state. Only explicitly confirmed simulator presentation attachment/removal may be shown as confirmed, isolated from runtime classifier input. If no confirmed state available, distinguish inferred or unknown. Do not use raw zero alone, flatline alone or connectivity as proof of removal. BIDMC replay has no wearable attachment evidence; use a text data-source panel. Never claim physical hardware exists.

| Presentation state | Trigger | Media | Text |
|---|---|---|---|
| attached_confirmed | Explicit authorized simulator attached state | attached video/still | Simulated wearable attached; actual receiving/degraded status separately |
| removed_confirmed | Explicit authorized simulator removed state | removed video/still | Simulated wearable removed; quality effects from actual backend |
| suspected_removal | Clinical artifact inference only | neutral still or last known state explicitly labeled | Probe removal suspected; verify sensor |
| unknown | no confirmation, disconnected or stale | no video; last known still only labeled historical | Attachment unknown; connection status independently |
| replay_not_applicable | BIDMC | no watch media | Recorded physiological replay |

On attachment restoration show attached only after confirmed presentation state; do not clear unresolved alert. Repeated same event must not restart video. Reset state on patient/session change. When live signal resumes but confirmation absent, say readings resumed, attachment unknown. If state arrives out of order, reject stale version. UI tests verify no false clinical inference. Media state never drives scoring or safety.

## Procedural spatial twin
Use Three.js/React Three Fiber only on Digital twin route, lazy loaded and optional. Scene: pure white background, matte sage central sphere or rounded solid, four smaller matte white physical nodes, thin neutral connectors, orthographic or low-perspective camera, soft ambient/directional lighting, modest contact shadows. No glass, hologram, particles, neon, decorative gradients, cursor-following beam, continuous spin, or animated organ model. No anatomical reconstruction claim. Central node is a visual metaphor for textual manifest, not data representation itself. Keep numeric labels in DOM overlay or accessible HTML alongside, always black/green and readable. Node selection via click and keyboard equivalent button list; selected object moves slightly forward (150–220ms), opens white evidence panel. Central selection opens manifest inspector. No auto-rotation necessary; optional bounded user orbit, reset view, reduced-motion static camera. Do not encode quantitative severity in arbitrary object size or color. Missing node label “Unavailable” and quality, no generated value. State switch Observed/Estimated/Forecast updates actual backend values and timestamp, never fabricated animation. Model unavailable renders textual state and 2D SVG graph. 3D must not be required for any clinical workflow.

## Counterfactual spatial panels
Only actual isolated backend branches. White neutral panels arranged horizontally or vertically, thin connectors and explicit labels, branch assumptions, outputs, uncertainty and limitations. Use simple CSS position transition, no scroll fade. Do not imply clinical treatment outcomes or causal effects. Original manifest/state remains unchanged.

## Performance checks
Verify assets load from local paths, no network dependency. Report sizes and decode errors; optimize copies if needed without overwriting originals. Use actual measured load/render performance; no claim of frame rate without test. Dispose GPU resources on unmount, pause hidden scene, cap device pixel ratio if needed. Static fallback must remain accessible. No 3D on overview, alerts or evaluation charts.
