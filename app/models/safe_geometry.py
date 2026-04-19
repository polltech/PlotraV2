from sqlalchemy import JSON
from geoalchemy2 import Geometry
from app.core.config import settings

def SafeGeometry(geometry_type='GEOMETRY', srid=4326):
    """
    Return a Geometry column if using PostgreSQL, 
    otherwise return a JSON column for SQLite compatibility.
    """
    if settings.database.async_url.startswith("postgresql"):
        return Geometry(geometry_type=geometry_type, srid=srid)
    return JSON
