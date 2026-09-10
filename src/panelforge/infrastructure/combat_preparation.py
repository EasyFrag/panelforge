"""Load an explicit, immutable Combat policy version at composition time."""
from pathlib import Path
from panelforge.application.combat_preparation import CombatRevisionPolicy
from panelforge.domain.video_preparation import VideoPreparationRef


def load_combat_revision_policy(blocks_root: Path, version: str = "1.0.0") -> CombatRevisionPolicy:
    preparation = VideoPreparationRef("combat", version)
    root = blocks_root / "h3-combat" / version
    contract = blocks_root / "h3-output-contracts" / "1.0.0"
    # The patch adopts the exact 1.1.0 choreography/audacity, never a latest alias.
    base = blocks_root / "h3-combat" / "1.1.0" if version in {"1.1.1", "1.2.0"} else root
    paths = [base / "choreography.system.txt"]
    if version in {"1.1.1", "1.2.0", "1.3.0"}:
        paths.append(blocks_root / "h3-combat" / "1.1.1" / "identity.system.txt")
    paths.extend((contract / "render-revision.system.txt", root / "render-revision.system.txt"))
    system = "\n\n".join(path.read_text(encoding="utf-8").strip() for path in paths)
    return CombatRevisionPolicy(preparation, system, ((blocks_root / "h3-combat" / "1.1.0" if version == "1.3.0" else base) / "audacity.system.txt").read_text(encoding="utf-8").strip())
