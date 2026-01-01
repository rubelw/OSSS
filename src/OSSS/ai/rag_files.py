from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

logger = logging.getLogger("OSSS.rag_files")

router = APIRouter()

PROJECT_ROOT = Path("/workspace")
INDEX_ROOT = PROJECT_ROOT / "vector_indexes" / "main"

RAG_PDF_ROOT = INDEX_ROOT / "pdfs"
RAG_IMG_ROOT = INDEX_ROOT / "images"


# ---------------------------------------------------------
# PDFs — accept FULL PATHS (with directories)
# ---------------------------------------------------------
@router.get("/rag-pdfs/main/{file_path:path}")
async def get_rag_pdf(file_path: str):
    """
    Example:
      /rag-pdfs/main/school_board/DCG-SchoolBoard/2025-6-10/special_meeting/attachments/Dr. Scott Blum 24-25...pdf
    """

    pdf_path = RAG_PDF_ROOT / file_path

    logger.debug("PDF request: %s", pdf_path)

    # Protect against path traversal
    try:
        pdf_path = pdf_path.resolve()
        if not str(pdf_path).startswith(str(RAG_PDF_ROOT.resolve())):
            raise HTTPException(status_code=403, detail="Invalid path")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")

    if not pdf_path.is_file():
        logger.warning("PDF not found: %s", pdf_path)
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=Path(file_path).name,
    )


# ---------------------------------------------------------
# Images — also accept FULL PATHS
# ---------------------------------------------------------
@router.get("/rag-images/main/{file_path:path}")
async def get_rag_image(file_path: str):
    """
    Example:
      /rag-images/main/school_board/DCG-SchoolBoard/2025-6-10/special_meeting/attachments/img123.jpeg
    """

    img_path = RAG_IMG_ROOT / file_path

    logger.debug("Image request: %s", img_path)

    # Path traversal protection
    try:
        img_path = img_path.resolve()
        if not str(img_path).startswith(str(RAG_IMG_ROOT.resolve())):
            raise HTTPException(status_code=403, detail="Invalid path")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")

    if not img_path.is_file():
        logger.warning("Image not found: %s", img_path)
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(img_path, filename=Path(file_path).name)