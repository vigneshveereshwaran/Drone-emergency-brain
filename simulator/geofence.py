"""
Simulator Geofence Manager.
Maintains simulated airspace boundaries, restricted areas, private properties, and legal hover zones.
"""

from typing import List, Dict, Any, Optional
import config


class GeofenceManager:
    """Manages airspace geofencing in the simulator."""

    def __init__(self):
        self.restricted_airspace = dict(config.RESTRICTED_AIRSPACE)
        self.private_property = dict(config.PRIVATE_PROPERTY)
        self.legal_hover_zones = [dict(hz) for hz in config.LEGAL_HOVER_ZONES]

    def is_in_restricted_zone(self, pos: List[float]) -> bool:
        """Checks if coordinate [x, y] is within restricted airspace (x: 42-62, y: 40-60)."""
        x, y = pos[0], pos[1]
        r = self.restricted_airspace
        return (r["x_min"] <= x <= r["x_max"] and r["y_min"] <= y <= r["y_max"])

    def is_in_private_property(self, pos: List[float]) -> bool:
        """Checks if coordinate [x, y] is within private property (x: 68-82, y: 30-45)."""
        x, y = pos[0], pos[1]
        p = self.private_property
        return (p["x_min"] <= x <= p["x_max"] and p["y_min"] <= y <= p["y_max"])

    def is_in_legal_hover_zone(self, pos: List[float]) -> Optional[Dict[str, Any]]:
        """
        Returns the hover zone dict if coordinate [x, y] is within any legal hover zone radius,
        otherwise returns None.
        """
        x, y = pos[0], pos[1]
        for hz in self.legal_hover_zones:
            cx, cy = hz["center"]
            radius = hz["radius"]
            dx = x - cx
            dy = y - cy
            if (dx * dx + dy * dy) <= (radius * radius):
                return hz
        return None

    def get_zone_type(self, pos: List[float]) -> str:
        """
        Determines the zone type at position pos:
        'RESTRICTED', 'PRIVATE', 'HOVER_ZONE', or 'ALLOWED'.
        """
        if self.is_in_restricted_zone(pos):
            return "RESTRICTED"
        if self.is_in_private_property(pos):
            return "PRIVATE"
        if self.is_in_legal_hover_zone(pos):
            return "HOVER_ZONE"
        return "ALLOWED"

    def get_map_metadata(self) -> Dict[str, Any]:
        """Returns structured map geometry for API and SVG rendering."""
        return {
            "map_size": config.MAP_SIZE,
            "start": config.START,
            "destination": config.DESTINATION,
            "restricted_airspace": self.restricted_airspace,
            "private_property": self.private_property,
            "legal_hover_zones": self.legal_hover_zones,
        }
