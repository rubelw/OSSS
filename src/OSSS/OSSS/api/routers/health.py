import logging
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/healthz", include_in_schema=False)
def healthz():
    # Temporarily suppress logging for this route
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)  # Suppress access logs
    logging.getLogger("OSSS.sessions").setLevel(logging.CRITICAL)  # Suppress session logs
    logging.getLogger("main").setLevel(logging.CRITICAL)  # Suppress 'main' logs

    response = {"status": "ok"}

    # Restore logging levels after request
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)  # Restore access logs level
    logging.getLogger("OSSS.sessions").setLevel(logging.INFO)  # Restore session logs level
    logging.getLogger("main").setLevel(logging.INFO)  # Restore 'main' logs level

    return response
