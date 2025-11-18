from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

logger = logging.getLogger("OSSS.rag_files")

router = APIRouter()

# Tailor these to your container paths
PROJECT_ROOT = Path("/workspace")  # adjust if different in your container
INDEX_ROOT = PROJECT_ROOT / "vector_indexes" / "main"

RAG_PDF_ROOT = INDEX_ROOT / "pdfs"
RAG_IMG_ROOT = INDEX_ROOT / "images"


@router.get("/rag-pdfs/main/{filename}")
async def get_rag_pdf(filename: str):
    """
    GET /rag-pdfs/main/DCG_BRAND_MANUAL.pdf
    """
    pdf_path = RAG_PDF_ROOT / filename

    logger.debug("PDF request: %s", pdf_path)

    if not pdf_path.is_file():
        logger.warning("PDF not found: %s", pdf_path)
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/rag-images/main/{filename:path}")
async def get_rag_image(filename: str):
    """
    GET /rag-images/main/DCG_BRAND_MANUAL_p12_352ffa7b.jpeg
    """
    img_path = RAG_IMG_ROOT / filename

    logger.debug("Image request: %s", img_path)

    if not img_path.is_file():
        logger.warning("Image not found: %s", img_path)
        raise HTTPException(status_code=404, detail="Image not found")

    # Let FastAPI infer media type; you can hardcode if you want
    return FileResponse(img_path, filename=filename)
