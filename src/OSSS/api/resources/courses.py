# Auto-generated resource for Courses (Catalog)
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.courses import Course
from OSSS.schemas.course import CourseCreate, CourseOut

router = build_crud_router(
    model=Course,
    schema_in=CourseCreate,
    schema_out=CourseOut,
    get_session=get_session,
    path_prefix="/sis/settings/catalog/courses",
    tags=["sis"],
)

register(Resource(name="courses", router=router, prefix=""))
