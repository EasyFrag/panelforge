"""Read-only compiler and deterministic retrieval for KREA2 wildcard packs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
import re
import secrets
from pathlib import Path
from typing import Callable, Iterable

import yaml

from panelforge.domain.krea2_assisted import Krea2PromptExample

from .prompt_examples import _classify


_TAG = re.compile(r"__([A-Za-z0-9][A-Za-z0-9._/-]*)__")
_INLINE = re.compile(r"\{([^{}]+)\}")
_WEIGHT = re.compile(r"^\s*(\d+(?:\.\d+)?)::(.*)$", re.DOTALL)
_ASPECT = re.compile(r"\s*\[(\d+)\s*:\s*(\d+)\]\s*\.?\s*$")
_WORDS = re.compile(r"[a-z0-9]+")
_MINOR_CODED = re.compile(
    r"\b(?:child|kid|minor|underage|preteen|teenager|schoolgirl|schoolboy|"
    r"high school|middle school|loli|shota|young girl|young boy)\b",
    re.IGNORECASE,
)
_EXPLICIT = re.compile(
    r"\b(?:anal|blow[ -]?job|cock|creampie|cum|cunnilingus|deepthroat|dick|"
    r"fellatio|fellation|fingering|foot[ -]?job|handjob|masturbat|naked|nude|"
    r"oral sex|penis|penetrat|pussy|sex|vagina)\b",
    re.IGNORECASE,
)
_PARTICIPANTS_FIELD = re.compile(
    r"(?:^|\.\s*)participants:\s*([^.]*)",
    re.IGNORECASE,
)
_ACTION_KEYS = {
    "anal_penetration", "vaginal_penetration", "penetration", "masturbation",
    "oral_sex", "footjob", "handjob", "exposure",
}
_STRUCTURAL_ACTION_KEYS = _ACTION_KEYS - {"exposure"}
_PARTICIPANT_TOPOLOGIES = {"solo", "pair", "group"}


@dataclass(frozen=True, slots=True)
class _Template:
    template_id: str
    short_id: str
    source_file: str
    source_line: int
    routers: tuple[str, ...]
    descriptor: str
    values: tuple[str, ...]
    eligible: bool
    nsfw: bool
    preview_path: Path | None
    tags: dict[str, tuple[str, ...]]


class LocalKrea2WildcardLibrary:
    """Loads one explicit wildcard pack without mutating its source files."""

    def __init__(
        self,
        source_root: str | Path | None,
        *,
        seed_factory: Callable[[], int] | None = None,
    ) -> None:
        self.source_root = Path(source_root).resolve() if source_root is not None else None
        self._seed_factory = seed_factory or (lambda: secrets.randbits(63))
        self._definitions: dict[str, tuple[str, ...]] = {}
        self._templates: tuple[_Template, ...] = ()
        self._by_id: dict[str, _Template] = {}
        self._state = "unavailable"
        self._error: str | None = None
        self._load()

    def status(self) -> dict[str, object]:
        return {
            "state": self._state,
            "error": self._error,
            "template_count": len(self._templates),
            "eligible_count": sum(template.eligible for template in self._templates),
            "source_count": len({template.source_file for template in self._templates}),
        }

    def search(self, query: str, *, limit: int = 3) -> tuple[Krea2PromptExample, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("la recherche V5 exige une intention")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        self._require_ready()
        query_tags = _query_tags(query)
        query_words = _word_set(query)
        explicit = bool(_EXPLICIT.search(query)) or bool(
            set(query_tags.get("actions", ())) & _ACTION_KEYS
        )
        ranked: list[tuple[float, _Template]] = []
        for template in self._templates:
            if not template.eligible or (template.nsfw and not explicit):
                continue
            score = _template_score(query_tags, query_words, template)
            ranked.append((score, template))
        ranked.sort(key=lambda item: (item[0], item[1].template_id), reverse=True)
        return tuple(
            self._compile_example(template, score, _relevance(query_tags, score, template))
            for score, template in ranked[:limit]
        )

    def recompile(self, example: Krea2PromptExample) -> Krea2PromptExample:
        self._require_ready()
        if example.source_kind != "wildcard" or not example.template_id:
            raise ValueError("Seule une inspiration wildcard V5 peut changer de variante.")
        try:
            template = self._by_id[example.template_id]
        except KeyError as error:
            raise KeyError(example.template_id) from error
        return self._compile_example(template, example.score, example.relevance)

    def preview_path(self, template_id: str) -> Path:
        self._require_ready()
        try:
            path = self._by_id[template_id].preview_path
        except KeyError as error:
            raise KeyError(template_id) from error
        if path is None or not path.is_file():
            raise FileNotFoundError(template_id)
        return path

    def _require_ready(self) -> None:
        if self._state != "ready":
            detail = f" : {self._error}" if self._error else ""
            raise RuntimeError("La bibliothèque de templates V5 n’est pas prête" + detail)

    def _load(self) -> None:
        if self.source_root is None or not self.source_root.is_dir():
            self._error = "Dossier wildcard absent. Configurez --krea2-wildcards-root."
            return
        try:
            documents: list[tuple[Path, dict[str, object]]] = []
            for path in sorted(self.source_root.glob("*.yaml")):
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError(f"document YAML invalide : {path.name}")
                documents.append((path, value))
                for root, node in value.items():
                    self._collect_definitions(str(root), node, path.name)
            for tag, values in self._definitions.items():
                for raw in values:
                    for reference in _TAG.findall(raw):
                        if reference not in self._definitions:
                            raise ValueError(
                                f"wildcard inconnue : {reference} (depuis {tag})"
                            )
            routers: dict[str, list[str]] = {}
            for tag, values in self._definitions.items():
                if "/router/" not in tag:
                    continue
                router = tag.rsplit("/", 1)[-1]
                for value in values:
                    for reference in _TAG.findall(value):
                        if "/template/" in reference:
                            routers.setdefault(reference, []).append(router)
            templates: list[_Template] = []
            for path, value in documents:
                if path.name.startswith("shared-"):
                    continue
                for root, node in value.items():
                    if not isinstance(node, dict) or not isinstance(node.get("template"), dict):
                        continue
                    for short_id, raw_values in node["template"].items():
                        if not isinstance(raw_values, list) or not all(
                            isinstance(item, str) for item in raw_values
                        ):
                            raise ValueError(f"template invalide : {root}/template/{short_id}")
                        template_id = f"{root}/template/{short_id}"
                        memberships = tuple(sorted(set(routers.get(template_id, ()))))
                        descriptor = " ".join(
                            (str(short_id), path.stem, *memberships)
                        ).replace("-", " ")
                        preview = (
                            path.with_name(path.stem + ".catalog")
                            / "template"
                            / f"{short_id}.png"
                        )
                        tags = _template_tags(descriptor)
                        templates.append(_Template(
                            template_id=template_id,
                            short_id=str(short_id),
                            source_file=path.name,
                            source_line=_source_line(path, str(short_id)),
                            routers=memberships,
                            descriptor=descriptor,
                            values=tuple(raw_values),
                            eligible=not bool(_MINOR_CODED.search(descriptor)),
                            nsfw="nsfw" in path.name.casefold(),
                            preview_path=preview if preview.is_file() else None,
                            tags=tags,
                        ))
            if not templates:
                raise ValueError("aucun template KREA2 trouvé")
            self._templates = tuple(sorted(templates, key=lambda item: item.template_id))
            self._by_id = {template.template_id: template for template in self._templates}
            if len(self._by_id) != len(self._templates):
                raise ValueError("identifiants de templates dupliqués")
            self._state, self._error = "ready", None
        except Exception as error:
            self._state, self._error = "failed", str(error)
            self._templates, self._by_id = (), {}

    def _collect_definitions(self, prefix: str, node: object, source: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                self._collect_definitions(f"{prefix}/{key}", value, source)
            return
        if isinstance(node, list) and all(isinstance(item, str) for item in node):
            values = tuple(node)
            previous = self._definitions.get(prefix)
            if previous is not None and previous != values:
                raise ValueError(f"définition wildcard dupliquée : {prefix} ({source})")
            self._definitions[prefix] = values

    def _compile_example(
        self,
        template: _Template,
        score: float,
        relevance: str,
    ) -> Krea2PromptExample:
        seed = int(self._seed_factory())
        rng = random.Random(seed)
        prompt = self._expand_choice(template.values, rng, stack=(template.template_id,))
        prompt = _expand_inline(prompt, rng)
        unresolved = _TAG.findall(prompt)
        if unresolved:
            raise ValueError(f"wildcard non résolue : {unresolved[0]}")
        aspect = None
        match = _ASPECT.search(prompt)
        if match:
            aspect = f"{match.group(1)}:{match.group(2)}"
            prompt = prompt[:match.start()]
        prompt = _clean(prompt)
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return Krea2PromptExample(
            example_id="wildcard-" + hashlib.sha256(
                f"{template.template_id}:{seed}".encode("utf-8")
            ).hexdigest()[:24],
            source_file=template.source_file,
            source_line=template.source_line,
            digest=digest,
            prompt=prompt,
            score=max(-1.0, min(1.0, score / 4.0)),
            relevance=relevance,
            actions=template.tags.get("actions", ()),
            participants=template.tags.get("participants", ()),
            interactions=template.tags.get("interactions", ()),
            positions=template.tags.get("positions", ()),
            framings=template.tags.get("framings", ()),
            settings=template.tags.get("settings", ()),
            source_kind="wildcard",
            template_id=template.template_id,
            variant_seed=seed,
            recommended_aspect_ratio=aspect,
        )

    def _expand_choice(
        self,
        values: Iterable[str],
        rng: random.Random,
        *,
        stack: tuple[str, ...],
    ) -> str:
        choices = list(values)
        if not choices:
            raise ValueError(f"pool wildcard vide : {stack[-1]}")
        weights: list[float] = []
        cleaned: list[str] = []
        for value in choices:
            weight, text = _weighted(value)
            weights.append(weight)
            cleaned.append(text)
        text = rng.choices(cleaned, weights=weights, k=1)[0]
        for _ in range(256):
            match = _TAG.search(text)
            if match is None:
                return text
            tag = match.group(1)
            if tag in stack:
                raise ValueError("cycle wildcard : " + " -> ".join((*stack, tag)))
            try:
                nested = self._definitions[tag]
            except KeyError as error:
                raise ValueError(f"wildcard inconnue : {tag}") from error
            replacement = self._expand_choice(nested, rng, stack=(*stack, tag))
            text = text[:match.start()] + replacement + text[match.end():]
        raise ValueError(f"expansion wildcard trop profonde : {stack[0]}")


def _template_score(
    query: dict[str, tuple[str, ...]],
    query_words: set[str],
    template: _Template,
) -> float:
    score = 0.0
    template_words = _word_set(template.descriptor)
    if query_words and template_words:
        score += 0.8 * len(query_words & template_words) / max(
            1, len(query_words | template_words)
        )
    for field, weight in (
        ("actions", 2.2), ("participants", 0.55), ("interactions", 0.7),
        ("positions", 0.55), ("framings", 0.4), ("settings", 0.5),
    ):
        requested = set(query.get(field, ()))
        available = set(template.tags.get(field, ()))
        if requested & available:
            score += weight
        elif requested and available:
            score -= weight * (0.9 if field == "actions" else 0.35)
        elif requested and field == "actions":
            score -= 1.6
    return score + _structural_adjustment(query, template.tags)


def _relevance(query: dict[str, tuple[str, ...]], score: float, template: _Template) -> str:
    if _structural_conflicts(query, template.tags):
        return "weak"
    requested_actions = set(query.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    available_actions = set(template.tags.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    action_match = _actions_match(requested_actions, available_actions)
    if requested_actions and not action_match:
        return "weak"
    if (action_match and score >= 1.6) or (not requested_actions and score >= 0.75):
        return "strong"
    return "medium" if score >= 0.15 else "weak"


def _query_tags(query: str) -> dict[str, tuple[str, ...]]:
    """Classify a V5 query and recover topology from its structured participants."""
    values = {key: list(items) for key, items in _classify(query).items()}
    match = _PARTICIPANTS_FIELD.search(query)
    if match is None:
        return {key: tuple(items) for key, items in values.items()}
    raw = match.group(1).strip()
    if raw.casefold() in {"", "none", "not specified", "unspecified", "n/a"}:
        return {key: tuple(items) for key, items in values.items()}
    participants = [
        item.strip()
        for item in re.split(r"\s*(?:,|\band\b)\s*", raw, flags=re.IGNORECASE)
        if item.strip()
    ]
    existing = set(values.get("participants", ())) & _PARTICIPANT_TOPOLOGIES
    if "group" in existing:
        values["participants"] = ["group"]
    elif len(participants) >= 3:
        values["participants"] = ["group"]
    elif len(participants) == 2:
        values["participants"] = ["pair"]
    elif len(participants) == 1:
        canonical = participants[0].casefold().strip()
        explicit = set(_classify(participants[0]).get("participants", ()))
        if canonical in _PARTICIPANT_TOPOLOGIES:
            explicit.add(canonical)
        values["participants"] = [
            next(
                (value for value in ("group", "pair", "solo") if value in explicit),
                "solo",
            )
        ]
    return {key: tuple(items) for key, items in values.items()}


def _template_tags(descriptor: str) -> dict[str, tuple[str, ...]]:
    """Add structural meaning carried by stable wildcard identifiers and routers."""
    values = {key: list(items) for key, items in _classify(descriptor).items()}
    words = _word_set(descriptor)

    def add(category: str, *labels: str) -> None:
        target = values[category]
        for label in labels:
            if label not in target:
                target.append(label)

    if words & {"oral", "blowjob", "deepthroat", "fellatio", "fellation", "blowbang"}:
        add("actions", "oral_sex")
        add("positions", "oral")
    if words & {"doggy", "doggystyle"}:
        add("actions", "penetration")
        add("positions", "doggy", "from_behind", "all_fours")
    if words & {"missionary", "cowgirl", "spooning", "penetration", "spitroast", "dp"}:
        add("actions", "penetration")
    if "anal" in words:
        add("actions", "anal_penetration", "penetration")
    if "vaginal" in words:
        add("actions", "vaginal_penetration", "penetration")
    if "footjob" in words:
        add("actions", "footjob")
        add("interactions", "foot_contact")
    if "handjob" in words:
        add("actions", "handjob")
    if words & {"group", "threesome", "multi", "spitroast", "blowbang", "dp"}:
        values["participants"] = ["group"]
        add("interactions", "group_contact")
        values["interactions"] = [
            item for item in values["interactions"] if item != "partner_contact"
        ]
    elif "partner" in words:
        values["participants"] = ["pair"]
        add("interactions", "partner_contact")
    if "solo" in words and not values["participants"]:
        values["participants"] = ["solo"]
    if "pov" in words:
        add("framings", "pov")
    return {key: tuple(items) for key, items in values.items()}


def _allowed_actions(requested: set[str]) -> set[str]:
    allowed = set(requested)
    if "penetration" in requested:
        allowed.add("vaginal_penetration")
    if "vaginal_penetration" in requested:
        allowed.add("penetration")
    if "anal_penetration" in requested:
        allowed.add("penetration")
    return allowed


def _actions_match(requested: set[str], available: set[str]) -> bool:
    return all(
        bool(_allowed_actions({action}) & available)
        for action in requested
    )


def _participant_topology(values: dict[str, tuple[str, ...]]) -> str | None:
    topologies = set(values.get("participants", ())) & _PARTICIPANT_TOPOLOGIES
    for topology in ("group", "pair", "solo"):
        if topology in topologies:
            return topology
    return None


def _structural_conflicts(
    query: dict[str, tuple[str, ...]],
    available: dict[str, tuple[str, ...]],
) -> bool:
    requested_actions = set(query.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    available_actions = set(available.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    if requested_actions and available_actions - _allowed_actions(requested_actions):
        return True
    requested_topology = _participant_topology(query)
    available_topology = _participant_topology(available)
    return bool(
        requested_topology
        and available_topology
        and requested_topology != available_topology
    )


def _structural_adjustment(
    query: dict[str, tuple[str, ...]],
    available: dict[str, tuple[str, ...]],
) -> float:
    requested_actions = set(query.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    available_actions = set(available.get("actions", ())) & _STRUCTURAL_ACTION_KEYS
    extra_actions = (
        available_actions - _allowed_actions(requested_actions)
        if requested_actions else set()
    )
    missing_actions = sum(
        not bool(_allowed_actions({action}) & available_actions)
        for action in requested_actions
    )
    adjustment = -2.4 * (len(extra_actions) + missing_actions)
    requested_topology = _participant_topology(query)
    available_topology = _participant_topology(available)
    if (
        requested_topology
        and available_topology
        and requested_topology != available_topology
    ):
        adjustment -= 2.4
    return adjustment


def _weighted(value: str) -> tuple[float, str]:
    match = _WEIGHT.match(value)
    if match is None:
        return 1.0, value.strip()
    return max(0.0001, float(match.group(1))), match.group(2).strip()


def _expand_inline(text: str, rng: random.Random) -> str:
    for _ in range(128):
        match = _INLINE.search(text)
        if match is None:
            return text
        values = match.group(1).split("|")
        weights, choices = zip(*(_weighted(value) for value in values))
        selected = rng.choices(list(choices), weights=list(weights), k=1)[0]
        text = text[:match.start()] + selected + text[match.end():]
    raise ValueError("trop de choix inline imbriqués")


def _source_line(path: Path, template_id: str) -> int:
    pattern = re.compile(rf"^\s+{re.escape(template_id)}:\s*$")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if pattern.match(line):
            return number
    return 1


def _word_set(value: str) -> set[str]:
    return set(_WORDS.findall(value.casefold().replace("é", "e")))


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,+", ",", value)
    value = re.sub(r"\s+([.;:])", r"\1", value)
    return value


__all__ = ["LocalKrea2WildcardLibrary"]
