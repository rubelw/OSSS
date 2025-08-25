# Auto-generated resource for Roles
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.roles import Role
from OSSS.schemas.role import RoleCreate, RoleOut

router = build_crud_router(
    model=Role,
    schema_in=RoleCreate,
    schema_out=RoleOut,
    get_session=get_session,
    path_prefix="/admin/settings/roles",
    tags=["admin"],
)

register(Resource(name="roles", router=router, prefix=""))
