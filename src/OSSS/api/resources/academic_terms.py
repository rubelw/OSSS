# Auto-generated resource for Academic Terms
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.academic_terms import AcademicTerm
from OSSS.schemas.academic_term import AcademicTermCreate, AcademicTermOut

router = build_crud_router(
    model=AcademicTerm,
    schema_in=AcademicTermCreate,
    schema_out=AcademicTermOut,
    get_session=get_session,
    path_prefix="/sis/settings/academic/terms",
    tags=["sis"],
)

register(Resource(name="academic_terms", router=router, prefix=""))
