"""OCR cleaning workflow for critical editions (Sources Chrétiennes).

Runs Mistral OCR on a PDF, then removes Greek text blocks and the
critical apparatus (collation lines, sigla lines), returning clean
markdown of the translation.
"""

import os
import re
from datetime import timedelta

from mistralai import workflows
from mistralai.client import Mistral
from pydantic import BaseModel

# --- Greek detection -------------------------------------------------------
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")


def _letter_stats(text: str) -> tuple[int, int]:
    letters = [c for c in text if c.isalpha()]
    greek = sum(1 for c in letters if GREEK_RE.match(c))
    return greek, len(letters)


def _is_greek_line(line: str, threshold: float) -> bool:
    greek, total = _letter_stats(line)
    if total == 0:
        return False
    return (greek / total) >= threshold


# --- Critical apparatus detection ------------------------------------------
# Lines like: "31 ORTMSHW /"  or  "34 b /"
_SIGLA_LINE_RE = re.compile(r"^\s*\d+(?:\s*[a-z])?\s*(?:[A-Z]{2,8})?\s*/?\s*$")
# Lines containing the collation separator "||"
_COLLATION_RE = re.compile(r"\|\|")
# Line-number refs with editorial verbs: "30, 5 post στόμα add. ..."
_EDITORIAL_VERBS_RE = re.compile(r"\b(om\.|add\.|post|del\.|cf\.|in marg\.|sup\.|scr\.|legg\.)\b")


def _is_apparatus_line(line: str) -> bool:
    if _COLLATION_RE.search(line):
        return True
    if _SIGLA_LINE_RE.match(line):
        return True
    if _EDITORIAL_VERBS_RE.search(line) and re.match(r"^\s*\d+([, ]\s*\d+)?\s+\S", line):
        return True
    return False


# --- Workflow ---------------------------------------------------------------
class ScCleanInput(BaseModel):
    """Input for the SC OCR cleaner.

    Provide exactly one of:
      - document_url: publicly accessible URL of the PDF
      - file_id: id of a PDF already uploaded via the Mistral Files API
    """

    document_url: str | None = None
    file_id: str | None = None
    remove_greek: bool = True
    remove_apparatus: bool = True
    remove_page_numbers: bool = True
    greek_threshold: float = 0.30
    page_separator: str = "\n\n"


def _get_client() -> Mistral:
    # Managed deployments expose a rotating service-account token file.
    token_path = os.environ.get("MISTRAL_SA_TOKEN_PATH")
    if token_path and os.path.exists(token_path) and not os.environ.get("MISTRAL_API_KEY"):
        with open(token_path) as f:
            os.environ["MISTRAL_API_KEY"] = f.read().strip()
    return Mistral(api_key=os.environ.get("MISTRAL_API_KEY") or None)


def _clean_page_markdown(md: str, params: ScCleanInput) -> str:
    kept: list[str] = []
    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if params.remove_page_numbers and re.fullmatch(r"\d{1,4}", stripped):
            continue
        if params.remove_greek and _is_greek_line(stripped, params.greek_threshold):
            continue
        if params.remove_apparatus and _is_apparatus_line(stripped):
            continue
        kept.append(line)
    out: list[str] = []
    for l in kept:
        if l == "" and (not out or out[-1] == ""):
            continue
        out.append(l)
    return "\n".join(out).strip()


@workflows.activity(
    start_to_close_timeout=timedelta(minutes=30),
    heartbeat_timeout=timedelta(seconds=60),
    retry_policy_max_attempts=3,
)
async def ocr_and_clean(params: ScCleanInput) -> dict:
    from mistralai.workflows import activity_heartbeat

    client = _get_client()

    if params.file_id:
        signed = client.files.get_signed_url(file_id=params.file_id)
        url = getattr(signed, "signed_url", None) or getattr(signed, "url", None)
        doc = {"type": "document_url", "document_url": url}
    elif params.document_url:
        doc = {"type": "document_url", "document_url": params.document_url}
    else:
        raise ValueError("Provide document_url or file_id")

    activity_heartbeat({"stage": "ocr"})

    pages_seen = 0
    cleaned_pages: list[str] = []
    ocr = client.ocr.process(model="mistral-ocr-latest", document=doc)
    for page in ocr.pages:
        pages_seen += 1
        cleaned_pages.append(_clean_page_markdown(page.markdown or "", params))
        if pages_seen % 10 == 0:
            activity_heartbeat({"stage": "clean", "pages": pages_seen})

    markdown = params.page_separator.join(p for p in cleaned_pages if p)
    return {
        "markdown": markdown,
        "pages": pages_seen,
        "pages_kept": sum(1 for p in cleaned_pages if p),
    }


@workflows.workflow.define(
    name="sc-ocr-cleaner",
    workflow_display_name="SC OCR Cleaner",
    workflow_description=(
        "OCR d'un PDF (éditions critiques Sources Chrétiennes) avec suppression "
        "du texte grec et de l'apparat critique. Retourne le markdown nettoyé."
    ),
)
class ScCleanWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: ScCleanInput) -> dict:
        return await ocr_and_clean(input)
