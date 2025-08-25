# Auto-generated resource for Departments
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.departments import Department
from OSSS.schemas.department import DepartmentCreate, DepartmentOut

router = build_crud_router(
    model=Department,
    schema_in=DepartmentCreate,
    schema_out=DepartmentOut,
    get_session=get_session,
    path_prefix="/admin/settings/departments",
    tags=["admin"],
)

register(Resource(name="departments", router=router, prefix=""))
