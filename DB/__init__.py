# In __init__.py
from .database import DB

# Makes DB available at package level
__all__ = ['DB']