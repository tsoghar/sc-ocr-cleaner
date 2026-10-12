# SC OCR Cleaner

Workflow Mistral Studio : OCR d'un PDF avec filtrage du texte grec et de
l'apparat critique, conçu pour les éditions Sources Chrétiennes (texte grec +
apparat + traduction française sur la même page).

## Workflow `sc-ocr-cleaner`

Entrée :

```json
{
  "document_url": "https://.../document.pdf",
  "file_id": null,
  "remove_greek": true,
  "remove_apparatus": true,
  "remove_page_numbers": true,
  "greek_threshold": 0.30,
  "page_separator": "\n\n"
}
```

- `document_url` **ou** `file_id` (fichier déjà uploadé via l'API Files, purpose `ocr`).
- `remove_greek` : supprime les lignes dont ≥ `greek_threshold` des lettres sont grecques.
- `remove_apparatus` : supprime les lignes de collation (`||`), les lignes de
  sigles (`31 ORTMSHW /`) et les leçons éditoriales (`30, 5 post στόμα add. ...`).
- `remove_page_numbers` : supprime les numéros de page isolés.

Sortie :

```json
{ "markdown": "...", "pages": 224, "pages_kept": 210 }
```

## Développement local

```bash
uv sync
MISTRAL_API_KEY=... uv run python -m src.worker
```
