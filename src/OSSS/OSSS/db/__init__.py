# src/OSSS/db/__init__.py
# Don't import session on package import; expose lazily instead
from .base import Base  # safe to import
# Optionally expose helpers lazily:
def get_session():  # returns async generator
    from .session import get_session as _get
    return _get()

def get_sessionmaker():
    from .session import get_sessionmaker as _gsm
    return _gsm()