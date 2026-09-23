"""Local, file-backed semantic scene library for KREA2 Assisted V4."""

from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock, Thread
from typing import Any, Iterable
import unicodedata

from panelforge.domain.krea2_assisted import Krea2PromptExample
from panelforge.domain.production import ComputeResource, ProductionWorkload


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INDEX_VERSION = 2
VECTOR_DIMENSION = 384

_MINOR_CODED = re.compile(
    r"\b(?:child(?:ren)?|kid(?:s)?|minor|underage|pre-?teen|teen(?:age|ager)?|"
    r"school\s*(?:girl|boy|uniform)|student\s+uniform|(?:high|middle)\s+school\s+student|"
    r"ecoliere|ecolier|lyceenne|lyceen|collegienne|collegien|uniforme\s+scolaire|"
    r"loli|shota|little\s+(?:girl|boy)|young\s+(?:girl|boy))\b",
    re.IGNORECASE,
)

_TAXONOMY: dict[str, dict[str, tuple[str, ...]]] = {
    "actions": {
        "anal_penetration": (
            "anal penetration", "penetrated anally", "anally penetrated", "anal sex",
            "penetration anale", "penetre analement", "penetrer analement",
            "maniere anale", "voie anale", "sodomie",
        ),
        "vaginal_penetration": (
            "vaginal penetration", "penetrated vaginally", "vaginally penetrated",
            "penetration vaginale", "penetre vaginalement",
        ),
        "penetration": (
            "penetration", "penetrating", "penetrated", "being entered",
            "se fait penetrer", "est penetree", "penetre par",
        ),
        "masturbation": (
            "masturbat", "fingers herself", "fingering herself", "fingers her",
            "self pleasure", "se masturbe", "se doigte",
        ),
        "oral_sex": ("oral sex", "fellatio", "cunnilingus", "blowjob", "fellation"),
        "kissing": ("kissing", "kiss", "embrasse", "baiser passionne"),
        "hugging": ("hugging", "embracing", "cuddling", "enlace", "calin"),
        "exposure": ("exposed genitals", "public exposure", "exhibitionist", "exhibe"),
    },
    "participants": {
        "solo": ("solo", "alone", "a woman", "a man", "une femme", "un homme"),
        "pair": (
            "couple", "two people", "deux personnes", "man and woman", "woman and man",
            "partner", "partenaire", "being penetrated", "se fait penetrer",
        ),
        "group": (
            "gangbang", "group sex", "multiple partners", "several partners", "several men",
            "multiple men", "two men", "three men", "plusieurs partenaires", "plusieurs hommes",
        ),
        "crowd": (
            "crowd", "crowded", "passengers", "people around", "public around",
            "foule", "bondé", "bonde", "passagers", "beaucoup de monde",
        ),
    },
    "interactions": {
        "self_directed": (
            "masturbat", "fingers herself", "fingering herself", "self pleasure",
            "se masturbe", "se doigte",
        ),
        "partner_contact": (
            "partner", "couple", "penetrated by", "being penetrated", "kissing",
            "partenaire", "se fait penetrer", "embrasse",
        ),
        "group_contact": (
            "gangbang", "group sex", "multiple partners", "several partners", "several men",
            "multiple men", "plusieurs partenaires", "plusieurs hommes",
        ),
    },
    "positions": {
        "standing": ("standing", "debout"),
        "sitting": ("sitting", "seated", "assis", "assise"),
        "lying": ("lying", "reclining", "allongé", "allongée"),
        "kneeling": ("kneeling", "à genoux", "agenouillé", "agenouillée"),
        "from_behind": ("from behind", "rear view", "vue de dos", "par derrière"),
        "bent_over": ("bent over", "leaning forward", "penche en avant", "courbee en avant"),
        "all_fours": ("on all fours", "a quatre pattes"),
        "legs_spread": ("legs spread", "legs apart", "jambes ecartees"),
        "straddling": ("straddling", "astride", "a califourchon"),
        "missionary": ("missionary", "missionnaire"),
        "cowgirl": ("cowgirl", "woman on top", "femme au-dessus"),
        "reverse_cowgirl": ("reverse cowgirl",),
        "doggy": ("doggy", "doggystyle", "on all fours", "à quatre pattes"),
        "lotus": ("lotus position", "position du lotus"),
        "spooning": ("spooning", "cuillère"),
        "oral": ("oral sex", "fellatio", "cunnilingus", "fellation"),
    },
    "framings": {
        "extreme_close_up": ("extreme close-up", "extreme closeup", "très gros plan"),
        "close_up": ("close-up", "closeup", "gros plan"),
        "medium": ("medium shot", "waist-up", "plan moyen", "plan taille"),
        "full_body": ("full-body", "full body", "head-to-toe", "en pied", "corps entier"),
        "wide": ("wide shot", "long shot", "plan large", "plan d'ensemble"),
        "pov": ("pov", "point-of-view", "first-person view", "vue subjective"),
        "overhead": ("overhead", "top-down", "bird's-eye", "vue du dessus", "plongée verticale"),
        "low_angle": ("low angle", "contre-plongée"),
    },
    "settings": {
        "bedroom": ("bedroom", "bedroom interior", "chambre"),
        "bathroom": ("bathroom", "shower", "bathtub", "salle de bain", "douche"),
        "hotel": ("hotel room", "hotel suite", "hôtel"),
        "studio": ("studio backdrop", "photo studio", "studio photo"),
        "living_room": ("living room", "salon"),
        "kitchen": ("kitchen", "cuisine"),
        "office": ("office", "bureau"),
        "outdoor": ("outdoor", "outside", "extérieur"),
        "beach": ("beach", "seaside", "plage"),
        "pool": ("swimming pool", "poolside", "piscine"),
        "forest": ("forest", "woods", "forêt"),
        "street": ("street", "city sidewalk", "rue"),
        "car": ("inside a car", "car interior", "dans une voiture"),
        "subway": (
            "subway car", "subway carriage", "metro car", "metro carriage", "train carriage",
            "inside a subway", "inside the metro", "wagon de metro", "dans le metro",
            "subway", "metro",
        ),
        "subway_platform": ("subway platform", "metro platform", "quai de metro"),
    },
}

_RERANK_WEIGHTS = {
    "actions": 0.14,
    "participants": 0.10,
    "interactions": 0.08,
    "positions": 0.06,
    "settings": 0.08,
    "framings": 0.04,
}


class LocalPromptExampleLibrary:
    """Owns source metadata, float16 vectors and CPU ONNX retrieval locally."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        library_id: str = "bunnys_wildcards_1",
        model_name: str = DEFAULT_MODEL,
        work_coordinator=None,
    ) -> None:
        self.library_id = library_id
        self.root = Path(workspace_root).resolve() / "prompt_libraries" / library_id
        self.source_root = self.root / "source"
        self.index_root = self.root / "index"
        self.model_root = Path(workspace_root).resolve() / "prompt_libraries" / "_models"
        self.model_name = model_name
        self.work_coordinator = work_coordinator
        self._lock = RLock()
        self._thread: Thread | None = None
        self._state = "ready" if self._index_is_current() else "unavailable"
        self._error: str | None = None
        self._progress = 1.0 if self._state == "ready" else 0.0
        self._examples: list[dict[str, Any]] | None = None
        self._vectors = None
        self._model = None

    def status(self) -> dict[str, object]:
        with self._lock:
            manifest = self._read_manifest()
            return {
                "library_id": self.library_id,
                "state": self._state,
                "progress": round(self._progress, 4),
                "error": self._error,
                "model": self.model_name,
                "dimension": VECTOR_DIMENSION,
                "example_count": int(manifest.get("example_count", 0)) if manifest else 0,
                "eligible_count": int(manifest.get("eligible_count", 0)) if manifest else 0,
                "source_count": int(manifest.get("source_count", 0)) if manifest else 0,
            }

    def start_indexing(self, *, force: bool = False) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            if not force and self._index_is_current():
                self._state, self._progress, self._error = "ready", 1.0, None
                return False
            self._state, self._progress, self._error = "queued", 0.0, None
            self._thread = Thread(
                target=self._index_worker,
                name=f"prompt-library-{self.library_id}",
                daemon=True,
            )
            self._thread.start()
            return True

    def search(self, query: str, *, limit: int = 3) -> tuple[Krea2PromptExample, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("la recherche V4 exige une intention")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        with self._lock:
            if self._state != "ready" or not self._index_is_current():
                detail = f" : {self._error}" if self._error else ""
                raise RuntimeError(
                    "La bibliothèque locale V4 n’est pas prête. Attendez la fin de son indexation"
                    + detail
                )
        np = _numpy()
        examples, vectors = self._load_index(np)
        vector = np.asarray(next(iter(self._embedding_model().query_embed(query))), dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if not norm:
            raise RuntimeError("l’encodeur local a produit une requête vide")
        vector /= norm
        eligible = np.asarray(
            [index for index, item in enumerate(examples) if item.get("eligible", True)],
            dtype=np.int64,
        )
        if not len(eligible):
            raise RuntimeError("la bibliothèque V4 ne contient aucun exemple utilisable")
        semantic = np.asarray(vectors[eligible], dtype=np.float32) @ vector
        pool_size = min(512, len(eligible))
        pool = np.argpartition(semantic, -pool_size)[-pool_size:]
        query_tags = _classify(query)
        ranked: list[tuple[float, float, int]] = []
        for local_index in pool:
            row = int(eligible[int(local_index)])
            item = examples[row]
            semantic_score = float(semantic[int(local_index)])
            score = semantic_score + _metadata_adjustment(query_tags, item)
            ranked.append((score, semantic_score, row))
        ranked.sort(reverse=True)
        selected: list[tuple[float, float, int]] = []
        deferred: list[tuple[float, float, int]] = []
        for candidate in ranked:
            item = examples[candidate[2]]
            if any(_near_duplicate(item, examples[chosen[2]]) for chosen in selected):
                deferred.append(candidate)
                continue
            selected.append(candidate)
            if len(selected) == limit:
                break
        if len(selected) < limit:
            selected.extend(deferred[:limit - len(selected)])
        return tuple(
            _domain_example(
                examples[row], score,
                _relevance_label(query_tags, examples[row], semantic_score),
            )
            for score, semantic_score, row in selected
        )

    def _index_worker(self) -> None:
        owner = f"prompt-library:{self.library_id}:index"
        lease = (
            self.work_coordinator.lease(
                owner,
                ComputeResource.LOCAL_GPU,
                ProductionWorkload.MAINTENANCE,
                "Indexation locale des exemples KREA2",
            )
            if self.work_coordinator is not None
            else nullcontext()
        )
        try:
            with lease:
                with self._lock:
                    self._state = "indexing"
                self._build_index(owner)
            with self._lock:
                self._state, self._progress, self._error = "ready", 1.0, None
                self._examples, self._vectors = None, None
        except Exception as error:
            with self._lock:
                self._state = "failed"
                self._error = str(error)[:1_000]

    def _build_index(self, owner: str) -> None:
        files = self._source_files()
        if not files:
            raise FileNotFoundError(f"Aucun fichier .txt dans {self.source_root}")
        examples, source_count = _read_examples(files)
        np = _numpy()
        model = self._embedding_model()
        if int(model.embedding_size) != VECTOR_DIMENSION:
            raise RuntimeError(
                f"dimension d’encodeur inattendue : {model.embedding_size}, attendu {VECTOR_DIMENSION}"
            )
        self.index_root.mkdir(parents=True, exist_ok=True)
        descriptor, vector_temp_name = tempfile.mkstemp(
            dir=self.index_root, prefix=".embeddings.", suffix=".f16"
        )
        os.close(descriptor)
        vector_temp = Path(vector_temp_name)
        examples_temp = self.index_root / ".examples.jsonl.tmp"
        manifest_temp = self.index_root / ".manifest.json.tmp"
        try:
            vectors = np.memmap(
                vector_temp,
                mode="w+",
                dtype=np.float16,
                shape=(len(examples), VECTOR_DIMENSION),
            )
            texts = (_embedding_text(item) for item in examples)
            for index, embedding in enumerate(model.passage_embed(texts, batch_size=64)):
                value = np.asarray(embedding, dtype=np.float32)
                norm = float(np.linalg.norm(value))
                vectors[index] = value / norm if norm else value
                if index % 32 == 0 or index + 1 == len(examples):
                    progress = 0.05 + (0.9 * ((index + 1) / len(examples)))
                    with self._lock:
                        self._progress = progress
                    if self.work_coordinator is not None:
                        self.work_coordinator.report_progress(
                            owner,
                            progress,
                            f"Indexation KREA2 · {index + 1}/{len(examples)}",
                        )
            vectors.flush()
            del vectors
            with examples_temp.open("w", encoding="utf-8", newline="\n") as stream:
                for item in examples:
                    stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            manifest = {
                "index_version": INDEX_VERSION,
                "library_id": self.library_id,
                "model": self.model_name,
                "dimension": VECTOR_DIMENSION,
                "dtype": "float16",
                "source_count": source_count,
                "example_count": len(examples),
                "eligible_count": sum(bool(item["eligible"]) for item in examples),
                "sources": _source_manifest(files),
            }
            manifest_temp.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            os.replace(vector_temp, self.index_root / "embeddings.f16")
            os.replace(examples_temp, self.index_root / "examples.jsonl")
            os.replace(manifest_temp, self.index_root / "manifest.json")
        finally:
            vector_temp.unlink(missing_ok=True)
            examples_temp.unlink(missing_ok=True)
            manifest_temp.unlink(missing_ok=True)

    def _embedding_model(self):
        with self._lock:
            if self._model is None:
                try:
                    from fastembed import TextEmbedding
                except ImportError as error:
                    raise RuntimeError(
                        "FastEmbed n’est pas installé dans l’environnement PanelForge"
                    ) from error
                self.model_root.mkdir(parents=True, exist_ok=True)
                self._model = TextEmbedding(
                    model_name=self.model_name,
                    cache_dir=str(self.model_root),
                    providers=["CPUExecutionProvider"],
                    cuda=False,
                    local_files_only=self._index_is_current(),
                )
            return self._model

    def _load_index(self, np):
        with self._lock:
            if self._examples is None:
                path = self.index_root / "examples.jsonl"
                self._examples = [
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            if self._vectors is None:
                self._vectors = np.memmap(
                    self.index_root / "embeddings.f16",
                    mode="r",
                    dtype=np.float16,
                    shape=(len(self._examples), VECTOR_DIMENSION),
                )
            return self._examples, self._vectors

    def _source_files(self) -> tuple[Path, ...]:
        if not self.source_root.is_dir() or self.source_root.is_symlink():
            return ()
        return tuple(sorted(
            (
                path
                for path in self.source_root.iterdir()
                if path.is_file() and not path.is_symlink() and path.suffix.lower() == ".txt"
            ),
            key=lambda path: ("(1)" in path.name, path.name.lower()),
        ))

    def _read_manifest(self) -> dict[str, Any] | None:
        path = self.index_root / "manifest.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        return value if isinstance(value, dict) else None

    def _index_is_current(self) -> bool:
        manifest = self._read_manifest()
        files = self._source_files()
        if not manifest or not files:
            return False
        return (
            manifest.get("index_version") == INDEX_VERSION
            and manifest.get("model") == self.model_name
            and manifest.get("dimension") == VECTOR_DIMENSION
            and manifest.get("sources") == _source_manifest(files)
            and (self.index_root / "examples.jsonl").is_file()
            and (self.index_root / "embeddings.f16").is_file()
        )


def _numpy():
    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError("NumPy n’est pas installé dans l’environnement PanelForge") from error
    return np


def _read_examples(files: Iterable[Path]) -> tuple[list[dict[str, Any]], int]:
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_count = 0
    for path in files:
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, raw in enumerate(stream, 1):
                prompt = raw.rstrip("\r\n")
                if not prompt.strip():
                    continue
                source_count += 1
                digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                tags = _classify(prompt)
                examples.append({
                    "example_id": f"scene-{digest[:20]}",
                    "source_file": path.name,
                    "source_line": line_number,
                    "digest": digest,
                    "prompt": prompt,
                    "eligible": _MINOR_CODED.search(_normalized_search_text(prompt)) is None,
                    **tags,
                })
    if not examples:
        raise ValueError("Le corpus local ne contient aucun prompt non vide")
    return examples, source_count


def _source_manifest(files: Iterable[Path]) -> list[dict[str, object]]:
    return [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ]


def _classify(text: str) -> dict[str, list[str]]:
    lowered = _normalized_search_text(text)
    result = {
        category: [
            label
            for label, needles in labels.items()
            if any(_normalized_search_text(needle) in lowered for needle in needles)
        ]
        for category, labels in _TAXONOMY.items()
    }
    participants = result["participants"]
    if "group" in participants:
        participants[:] = [value for value in participants if value not in {"solo", "pair"}]
    elif "pair" in participants:
        participants[:] = [value for value in participants if value != "solo"]
    interactions = result["interactions"]
    if "group_contact" in interactions:
        interactions[:] = [value for value in interactions if value != "partner_contact"]
    return result


def _normalized_search_text(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value)


def _embedding_text(item: dict[str, Any]) -> str:
    metadata = "; ".join(
        f"{category}: {', '.join(item.get(category, [])) or 'unspecified'}"
        for category in (
            "actions", "participants", "interactions", "positions", "framings", "settings"
        )
    )
    return f"{metadata}. Scene prompt: {item['prompt']}"


def _metadata_adjustment(query: dict[str, list[str]], item: dict[str, Any]) -> float:
    adjustment = 0.0
    for category, weight in _RERANK_WEIGHTS.items():
        requested = set(query.get(category, []))
        if not requested:
            continue
        present = set(item.get(category, []))
        overlap = len(requested & present) / len(requested)
        adjustment += weight * overlap
        if not present:
            adjustment -= weight * 0.15
        elif not overlap:
            adjustment -= weight * 0.5
    return adjustment


def _metadata_coverage(query: dict[str, list[str]], item: dict[str, Any]) -> float | None:
    requested_weight = 0.0
    matched_weight = 0.0
    for category, weight in _RERANK_WEIGHTS.items():
        requested = set(query.get(category, []))
        if not requested:
            continue
        requested_weight += weight
        present = set(item.get(category, []))
        matched_weight += weight * (len(requested & present) / len(requested))
    return matched_weight / requested_weight if requested_weight else None


def _relevance_label(
    query: dict[str, list[str]],
    item: dict[str, Any],
    semantic_score: float,
) -> str:
    coverage = _metadata_coverage(query, item)
    if coverage is None:
        return "strong" if semantic_score >= 0.65 else "medium" if semantic_score >= 0.48 else "weak"
    if semantic_score >= 0.35 and coverage >= 0.65:
        return "strong"
    if (semantic_score >= 0.30 and coverage >= 0.25) or (
        semantic_score >= 0.62 and coverage >= 0.15
    ):
        return "medium"
    return "weak"


def _near_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for category in ("actions", "participants", "interactions"):
        left_tags = set(left.get(category, []))
        right_tags = set(right.get(category, []))
        if left_tags and right_tags and left_tags.isdisjoint(right_tags):
            return False
    left_tokens = set(re.findall(r"[a-z0-9]+", _normalized_search_text(left["prompt"])))
    right_tokens = set(re.findall(r"[a-z0-9]+", _normalized_search_text(right["prompt"])))
    if min(len(left_tokens), len(right_tokens)) < 18:
        return False
    overlap = len(left_tokens & right_tokens)
    containment = overlap / min(len(left_tokens), len(right_tokens))
    union = len(left_tokens | right_tokens)
    return containment >= 0.82 and bool(union) and overlap / union >= 0.45


def _domain_example(item: dict[str, Any], score: float, relevance: str) -> Krea2PromptExample:
    return Krea2PromptExample(
        example_id=item["example_id"],
        source_file=item["source_file"],
        source_line=int(item["source_line"]),
        digest=item["digest"],
        prompt=item["prompt"],
        score=round(score, 6),
        relevance=relevance,
        actions=tuple(item.get("actions", [])),
        participants=tuple(item.get("participants", [])),
        interactions=tuple(item.get("interactions", [])),
        positions=tuple(item.get("positions", [])),
        framings=tuple(item.get("framings", [])),
        settings=tuple(item.get("settings", [])),
    )


__all__ = ["DEFAULT_MODEL", "LocalPromptExampleLibrary"]
