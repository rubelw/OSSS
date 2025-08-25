# Auto-generated resource for Permissions
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.permissions import Permission
from OSSS.schemas.permission import PermissionCreate, PermissionOut

router = build_crud_router(
    model=Permission,
    schema_in=PermissionCreate,
    schema_out=PermissionOut,
    get_session=get_session,
    path_prefix="/admin/settings/permissions",
    tags=["admin"],
)

register(Resource(name="permissions", router=router, prefix=""))
