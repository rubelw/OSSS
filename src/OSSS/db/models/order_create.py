# re-export to keep old import paths working, without redefining the table
from .order_line_items import OrderLineItem
__all__ = ["OrderLineItem"]
