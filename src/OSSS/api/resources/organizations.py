# Auto-generated resource for Organizations
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.organizations import Organization
from OSSS.schemas.organization import OrganizationCreate, OrganizationOut

router = build_crud_router(
    model=Organization,
    schema_in=OrganizationCreate,
    schema_out=OrganizationOut,
    get_session=get_session,
    path_prefix="/admin/settings/organizations",
    tags=["admin"],
)

register(Resource(name="organizations", router=router, prefix=""))
