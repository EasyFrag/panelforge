"""Bounded CSV import; each CSV record is an intention, including multiline fields."""
import csv
import io

from panelforge.domain.creation_batch import CreationIntent, MAX_BATCH_ITEMS, MAX_CSV_BYTES


def parse_intentions_csv(content: bytes) -> tuple[tuple[CreationIntent, ...], int]:
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("Le CSV dépasse 8 Mio.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Enregistre le CSV en UTF-8.") from error
    if "\x00" in text:
        raise ValueError("Le CSV contient un caractère nul.")
    # Detect using the header only: punctuation inside intentions is not a delimiter hint.
    header_line = next((line for line in text.splitlines() if line.strip()), "")
    delimiter = ";" if ";" in header_line else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next((row for row in reader if any(cell.strip() for cell in row)), [])
        header = [cell.strip().casefold() for cell in header]
        if header.count("intention") != 1 or len(set(header)) != len(header):
            raise ValueError("Le CSV doit avoir une colonne intention unique (nom est facultatif).")
        if any(field not in {"nom", "intention"} for field in header):
            raise ValueError("Colonnes acceptées : intention et nom (facultatif).")
        intentions, ignored = [], 0
        for row in reader:
            if not any(cell.strip() for cell in row):
                ignored += 1
                continue
            if len(row) != len(header):
                raise ValueError(f"Ligne {reader.line_num} : nombre de colonnes incorrect. Entoure les textes de guillemets.")
            values = dict(zip(header, (cell.strip() for cell in row)))
            if not values["intention"]:
                ignored += 1
                continue
            try:
                intentions.append(CreationIntent(values.get("nom") or f"Intention {len(intentions) + 1}", values["intention"]))
            except ValueError as error:
                raise ValueError(f"Ligne {reader.line_num} : {error}") from error
            if len(intentions) > MAX_BATCH_ITEMS:
                raise ValueError(f"Un batch accepte au maximum {MAX_BATCH_ITEMS} intentions.")
    except csv.Error as error:
        raise ValueError(f"CSV invalide près de la ligne {reader.line_num} : {error}") from error
    if not intentions:
        raise ValueError("Aucune intention non vide trouvée.")
    return tuple(intentions), ignored
