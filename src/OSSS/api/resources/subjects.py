# Auto-generated resource for Subjects
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.subjects import Subject
from OSSS.schemas.subject import SubjectCreate, SubjectOut

router = build_crud_router(
    model=Subject,
    schema_in=SubjectCreate,
    schema_out=SubjectOut,
    get_session=get_session,
    path_prefix="/admin/settings/subjects",
    tags=["admin"],
)

register(Resource(name="subjects", router=router, prefix=""))
