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

## Commands

- Tests: `python -m unittest discover -s tests`
