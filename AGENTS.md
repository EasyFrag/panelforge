# Project instructions (PanelForge)

## Always start here

- Read `.agent/CONTINUITY.md` before changing code.
- Keep Goal / Current state / Next steps accurate.

## Architecture

- Keep the project a modular monolith.
- `domain` must not import infrastructure or vendor SDKs.
- ComfyUI node IDs belong in versioned workflow manifests, not feature code.
- Do not copy large legacy LocalQ modules. Port only a small behavior with tests when needed.
- Prefer explicit contracts and IDs over filesystem discovery conventions.

## Work style

- Keep diffs small and reviewable.
- Add dependencies only for an implemented need.
- Update `.agent/CONTINUITY.md` at the end of each task.
- Tests are run by the user unless explicitly requested otherwise. Do not launch LLM calls or image/video generations for verification; the user may be generating concurrently. Do not restart running services during implementation without an explicit request.

## Commands

- Tests: `python -m unittest discover -s tests`
