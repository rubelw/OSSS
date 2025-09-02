# src/OSSS/tests/test_ap_vendor_mapping.py
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm.exc import UnmappedClassError

from OSSS.db.models.ap_vendors import ApVendor, ApVendorBase


def _is_mapped(cls) -> bool:
    """
    Return True if SQLAlchemy has a Mapper for cls, False otherwise.
    Works across SA 1.4/2.x.
    """
    try:
        inspect(cls)  # raises if not mapped
        return True
    except (NoInspectionAvailable, UnmappedClassError, TypeError, AttributeError):
        return False


def test_ap_vendor_mapping():
    # ApVendor must be a mapped class
    assert _is_mapped(ApVendor), "ApVendor should be an ORM-mapped class"
    # And its mapper should point back to the same class
    assert inspect(ApVendor).class_ is ApVendor

    # The mixin/base must NOT be mapped
    assert not _is_mapped(ApVendorBase), "ApVendorBase (mixin) should not be mapped"
