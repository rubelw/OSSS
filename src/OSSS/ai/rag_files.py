from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

# Dedicated logger for all RAG file-serving operations.
# This makes it easy to trace PDF/image access and catch path issues.
logger = logging.getLogger("OSSS.rag_files")

# This router is meant to be included into your main FastAPI app:
#     app.include_router(router, prefix="")
router = APIRouter()

# ----------------------------------------------------------------------
# Root locations for RAG-related assets
# ----------------------------------------------------------------------
# PROJECT_ROOT is the base of your checked-out workspace inside the container.
# In dev, this is typically /workspace (as mounted by your Docker setup).
PROJECT_ROOT = Path("/workspace")

# INDEX_ROOT is the root of your *main* RAG index. If you later add
# additional indexes (e.g. "tutor", "agent"), you could create separate
# routers or parameterize this.
INDEX_ROOT = PROJECT_ROOT / "vector_indexes" / "main"

# Within the main index, we keep:
#   - `pdfs/`   : original PDFs copied over by your indexing process
#   - `images/` : extracted images / snapshots associated with those PDFs
RAG_PDF_ROOT = INDEX_ROOT / "pdfs"
RAG_IMG_ROOT = INDEX_ROOT / "images"


# ======================================================================
# PDF Serving Endpoint
# ======================================================================
@router.get("/rag-pdfs/main/{file_path:path}")
async def get_rag_pdf(file_path: str):
    """
    Serve an indexed PDF from the RAG `main` index.

    This endpoint allows nested directory paths, for example:

        /rag-pdfs/main/school_board/DCG-SchoolBoard/2025-6-10/special_meeting/attachments/Dr. Scott Blum 24-25...pdf

    Parameters
    ----------
    file_path : str
        The relative path from the RAG_PDF_ROOT directory to the PDF file.
        This may contain subdirectories (FastAPI's `:path` converter).

    Returns
    -------
    FileResponse
        A streamed PDF response if the file exists and is allowed.

    Security Notes
    --------------
    - We always resolve the resulting path and ensure it is still *under*
      RAG_PDF_ROOT. This prevents directory traversal attacks such as
      `../../../etc/passwd`.
    - If the resolved path escapes RAG_PDF_ROOT, a 403 is returned.
    """
    # Construct the filesystem path by joining the root with the requested path.
    pdf_path = RAG_PDF_ROOT / file_path

    logger.debug("PDF request: %s", pdf_path)

    # ------------------------------------------------------------------
    # Path traversal protection
    # ------------------------------------------------------------------
    try:
        # Resolve returns an absolute path with any ".." components
        # normalized. This is essential to safely compare against the
        # allowed root directory.
        pdf_path = pdf_path.resolve()

        # Ensure the final resolved path is still within the allowed root.
        # If someone tries "../../../", this check will fail.
        if not str(pdf_path).startswith(str(RAG_PDF_ROOT.resolve())):
            logger.warning(
                "Rejected PDF path outside RAG_PDF_ROOT: %s (root=%s)",
                pdf_path,
                RAG_PDF_ROOT.resolve(),
            )
            raise HTTPException(status_code=403, detail="Invalid path")
    except Exception:
        # Any error in resolving the path should be treated as a security
        # issue and rejected with a generic 403.
        raise HTTPException(status_code=403, detail="Invalid path")

    # ------------------------------------------------------------------
    # Check for existence
    # ------------------------------------------------------------------
    if not pdf_path.is_file():
        logger.warning("PDF not found: %s", pdf_path)
        raise HTTPException(status_code=404, detail="PDF not found")

    # ------------------------------------------------------------------
    # Return FileResponse
    # ------------------------------------------------------------------
    # We expose the file with mime type "application/pdf" and a filename that
    # is just the final path component (no directories).
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=Path(file_path).name,
    )


# ======================================================================
# Image Serving Endpoint
# ======================================================================
@router.get("/rag-images/main/{file_path:path}")
async def get_rag_image(file_path: str):
    """
    Serve an image associated with a RAG PDF from the `main` index.

    This API mirrors the PDF endpoint but for images:

        /rag-images/main/school_board/DCG-SchoolBoard/2025-6-10/special_meeting/attachments/img123.jpeg

    Parameters
    ----------
    file_path : str
        The relative path from the RAG_IMG_ROOT directory to the image file.
        May contain nested directories.

    Returns
    -------
    FileResponse
        A streamed file response (content-type inferred by FastAPI/starlette)
        if the image exists and is allowed.

    Security Notes
    --------------
    - Uses the same path resolution + prefix check as the PDF route to guard
      against directory traversal.
    """
    # Build the expected absolute path under the images root.
    img_path = RAG_IMG_ROOT / file_path

    logger.debug("Image request: %s", img_path)

    # ------------------------------------------------------------------
    # Path traversal protection
    # ------------------------------------------------------------------
    try:
        img_path = img_path.resolve()
        if not str(img_path).startswith(str(RAG_IMG_ROOT.resolve())):
            logger.warning(
                "Rejected image path outside RAG_IMG_ROOT: %s (root=%s)",
                img_path,
                RAG_IMG_ROOT.resolve(),
            )
            raise HTTPException(status_code=403, detail="Invalid path")
    except Exception:
        # Reject any malformed or unsafe path.
        raise HTTPException(status_code=403, detail="Invalid path")

    # ------------------------------------------------------------------
    # Existence check
    # ------------------------------------------------------------------
    if not img_path.is_file():
        logger.warning("Image not found: %s", img_path)
        raise HTTPException(status_code=404, detail="Image not found")

    # ------------------------------------------------------------------
    # Response
    # ------------------------------------------------------------------
    # We let FileResponse infer the appropriate content-type from the file
    # extension. The `filename` shown to the client is just the last path
    # component, not the full directory structure.
    return FileResponse(
        img_path,
        filename=Path(file_path).name,
    )
