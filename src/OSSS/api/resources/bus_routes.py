# Auto-generated resource for Bus Routes
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.bus_routes import BusRoute
from OSSS.schemas.bus_route import BusRouteCreate, BusRouteOut

router = build_crud_router(
    model=BusRoute,
    schema_in=BusRouteCreate,
    schema_out=BusRouteOut,
    get_session=get_session,
    path_prefix="/transport/bus-routes",
    tags=["transport"],
)

register(Resource(name="bus_routes", router=router, prefix=""))
