from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError

from OSSS.db.models.ap_vendors import ApVendor, ApVendorBase

def test_ap_vendor_mapping():
    # must succeed
    assert ApVendor.__mapper__.class_ is ApVendor

    # must FAIL (i.e., not mapped)
    try:
        class_mapper(ApVendorBase)
        raise AssertionError("Mixin is incorrectly mapped!")
    except UnmappedClassError:
        pass
