# ==========================
# File: dummy_map_server.py
# Improved POI matching with plural & synonyms support
# ==========================
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional

@dataclass(frozen=True)
class DummyServerParams:
    name: str = "dummy"
    command: str = "python"
    args: Tuple[str, ...] = ("-m", "servers.dummy_map_server",)

class DummyMapServer:
    def __init__(self, params: Optional[DummyServerParams] = None):
        self.params = params or DummyServerParams()

        # Dummy dataset
        self.places: List[Dict[str, Any]] = [
            {"name": "Central Park", "lat": 40.785091, "lon": -73.968285, "category": "park"},
            {"name": "Alice's Restaurant", "lat": 40.77, "lon": -73.98, "category": "restaurant"},
            {"name": "Bob's Coffee Shop", "lat": 40.775, "lon": -73.97, "category": "cafe"},
            {"name": "City Library", "lat": 40.7532, "lon": -73.9822, "category": "library"},
        ]

        # Category synonyms & plural support
        self.category_synonyms = {
            "restaurant": ["restaurant", "restaurants", "food", "dining", "eat"],
            "cafe": ["cafe", "cafes", "coffee", "coffeeshop"],
            "library": ["library", "libraries", "books"],
            "park": ["park", "parks"],
        }

    # -------------------------------
    # GEOCODE
    # -------------------------------
    def geocode(self, query: str) -> List[Dict[str, Any]]:
        if not query:
            return []
        q = query.lower()
        return [
            {"name": p["name"], "lat": p["lat"], "lon": p["lon"]}
            for p in self.places
            if q in p["name"].lower()
        ]

    # -------------------------------
    # RESOLVE INPUT (name or coords)
    # -------------------------------
    def _resolve(self, loc: Any) -> Optional[Dict[str, float]]:
        if isinstance(loc, str):
            res = self.geocode(loc)
            return res[0] if res else None
        if isinstance(loc, (tuple, list)) and len(loc) == 2:
            return {"lat": float(loc[0]), "lon": float(loc[1])}
        if isinstance(loc, dict) and "lat" in loc and "lon" in loc:
            return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
        return None

    # -------------------------------
    # ROUTE
    # -------------------------------
    def route(self, origin: Any, destination: Any) -> Dict[str, Any]:
        orig = self._resolve(origin)
        dest = self._resolve(destination)

        if not orig or not dest:
            return {"error": "Origin or destination not found."}

        R = 6371.0
        phi1, phi2 = math.radians(orig["lat"]), math.radians(dest["lat"])
        dphi = math.radians(dest["lat"] - orig["lat"])
        dlmb = math.radians(dest["lon"] - orig["lon"])

        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist = R * c

        minutes = (dist / 50.0) * 60.0
        return {"distance_km": round(dist, 3), "duration_min": round(minutes, 1)}

    # -------------------------------
    # POI SEARCH (IMPROVED)
    # -------------------------------
    def search_poi(self, query: Optional[str] = None, near: Any | None = None) -> List[Dict[str, Any]]:
        if not query:
            return []

        q = query.lower().strip()
        q_base = q.rstrip("s")  # plural handling
        center = self._resolve(near) if near else None

        results: List[Dict[str, Any]] = []

        for p in self.places:
            name = p["name"].lower()
            category = p["category"].lower()

            # Name match
            name_match = q in name

            # Category match using synonyms & plural handling
            category_list = self.category_synonyms.get(category, [])
            category_match = any(q_base == c.rstrip("s") for c in category_list)

            if not (name_match or category_match):
                continue

            # If searching near a place → filter by distance
            if center:
                R = 6371.0
                dphi = math.radians(p["lat"] - center["lat"])
                dlmb = math.radians(p["lon"] - center["lon"])

                phi1, phi2 = math.radians(center["lat"]), math.radians(p["lat"])
                a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                dist = R * c

                if dist > 5.0:  # 5km radius
                    continue

                results.append({
                    "name": p["name"],
                    "category": p["category"],
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "distance_km": round(dist, 3)
                })
            else:
                # No "near" filter
                results.append({
                    "name": p["name"],
                    "category": p["category"],
                    "lat": p["lat"],
                    "lon": p["lon"]
                })

        if center:
            results.sort(key=lambda r: r.get("distance_km", 0.0))

        return results
