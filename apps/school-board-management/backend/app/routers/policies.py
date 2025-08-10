from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, schemas
from typing import List
from ..auth import current_user
from ..utils.diff import redline_html

router = APIRouter(prefix="/policies", tags=["policies"])

@router.post("/", response_model=schemas.Policy)
def create_policy(payload: schemas.PolicyIn, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    p = models.Policy(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get("/", response_model=List[schemas.Policy])
def list_policies(db: Session = Depends(get_db)):
    return db.query(models.Policy).order_by(models.Policy.code.asc()).all()

@router.get("/{policy_id}", response_model=schemas.PolicyDetail)
def get_policy(policy_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Policy, policy_id)
    if not p:
        raise HTTPException(404, "Policy not found")
    versions = (db.query(models.PolicyVersion)
                  .filter(models.PolicyVersion.policy_id == policy_id)
                  .order_by(models.PolicyVersion.version_no.asc())
                  .all())
    return schemas.PolicyDetail(
        id=p.id, code=p.code, title=p.title, status=p.status, category=p.category,
        versions=[schemas.PolicyVersionMeta.model_validate(v) for v in versions]
    )

@router.get("/{policy_id}/versions/{version_id}", response_model=schemas.PolicyVersionBody)
def get_policy_version(policy_id: int, version_id: int, db: Session = Depends(get_db)):
    v = db.get(models.PolicyVersion, version_id)
    if not v or v.policy_id != policy_id:
        raise HTTPException(404, "Version not found")
    return schemas.PolicyVersionBody.model_validate(v)

@router.get("/{policy_id}/diff", response_class=Response)
def policy_diff(policy_id: int, from_id: int, to_id: int, db: Session = Depends(get_db)):
    a = db.get(models.PolicyVersion, from_id)
    b = db.get(models.PolicyVersion, to_id)
    if not a or not b or a.policy_id != policy_id or b.policy_id != policy_id:
        raise HTTPException(404, "Version(s) not found")
    html = redline_html(a.body_md or "", b.body_md or "")
    return Response(content=html, media_type="text/html")
