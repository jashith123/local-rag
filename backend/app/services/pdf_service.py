from pathlib import Path

from pypdf import PdfReader


class PDFExtractionError(Exception):
    pass


def extract_pages(file_path: Path) -> list[str]:
    """Return the text of each page, in order.

    Pages are kept separate rather than concatenated because we will eventually
    want to cite "page 7" back to the user in a chat answer.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as exc:
        raise PDFExtractionError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        # An empty password unlocks a surprising number of "protected" PDFs.
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFExtractionError("PDF is password protected") from exc

    pages = []
    for page in reader.pages:
        try:
            pages.append((page.extract_text() or "").strip())
        except Exception:
            # One malformed page should not lose the other 200.
            pages.append("")
    return pages


def extract_text(file_path: Path) -> str:
    return "\n\n".join(page for page in extract_pages(file_path) if page)
