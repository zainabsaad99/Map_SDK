# =============================
# File: openstreetmap_server.py
# =============================
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import requests, urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(frozen=True)
class OpenStreetMapServerParams:
    name: str = "openstreetmap"
    nominatim_search_url: str = "https://nominatim.openstreetmap.org/search"
    nominatim_reverse_url: str = "https://nominatim.openstreetmap.org/reverse"
    osrm_route_url: str = "http://router.project-osrm.org/route/v1/driving"
    osrm_table_url: str = "http://router.project-osrm.org/table/v1/driving"
    overpass_endpoints: Tuple[str, ...] = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    )
    user_agent: str = "MapServerDemo/1.1"
    timeout_s: int = 12
    retry_total: int = 3
    retry_backoff: float = 0.5


class OpenStreetMapServer:
    """Production-minded wrapper around Nominatim + OSRM (+ optional Overpass).

    Exposes at least three distinct operations:
      1) geocode(address: str)
      2) reverse_geocode(lat: float, lon: float)
      3) route(origin: Any, destination: Any)
      4) matrix(places: list[Any])  # distance/time matrix (bonus)
    """

    def __init__(self, params: Optional[OpenStreetMapServerParams] = None):
        self.p = params or OpenStreetMapServerParams()
        self.headers = {"User-Agent": self.p.user_agent}
        # Robust session with retries and backoff
        self.session = requests.Session()
        retry = Retry(
            total=self.p.retry_total,
            read=self.p.retry_total,
            connect=self.p.retry_total,
            backoff_factor=self.p.retry_backoff,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _request_json(self, url: str, *, params: Optional[Dict[str, Any]] = None, data: Optional[str] = None) -> Dict[str, Any] | List[Any]:
        try:
            if data is not None:
                resp = self.session.post(url, params=params, data=data, headers=self.headers, timeout=self.p.timeout_s)
            else:
                resp = self.session.get(url, params=params, headers=self.headers, timeout=self.p.timeout_s)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    def _resolve(self, loc: Any) -> Optional[Dict[str, float]]:
        if isinstance(loc, str):
            res = self.geocode(loc)
            return res[0] if res else None
        if isinstance(loc, (tuple, list)) and len(loc) == 2:
            return {"lat": float(loc[0]), "lon": float(loc[1])}
        if isinstance(loc, dict) and "lat" in loc and "lon" in loc:
            return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
        return None

    # -----------------------------
    # 1) Geocoding using Nominatim
    # -----------------------------
    def geocode(self, address: str) -> List[Dict[str, Any]]:
        if not address:
            return []
        params = {"q": address, "format": "json", "limit": 3}
        url = self.p.nominatim_search_url
        data = self._request_json(url, params=params)
        if isinstance(data, dict) and data.get("error"):
            return [{"error": data["error"]}]
        results: List[Dict[str, Any]] = []
        for i in data:  # type: ignore[assignment]
            if "lat" in i and "lon" in i:
                try:
                    results.append({
                        "display_name": i.get("display_name", ""),
                        "lat": float(i["lat"]),
                        "lon": float(i["lon"])
                    })
                except Exception:
                    continue
        return results

    # ---------------------------------
    # 2) Reverse Geocoding (new)
    # ---------------------------------
    def reverse_geocode(self, lat: float, lon: float) -> Dict[str, Any]:
        params = {"format": "json", "lat": lat, "lon": lon}
        url = self.p.nominatim_reverse_url
        data = self._request_json(url, params=params)
        if isinstance(data, dict) and data.get("error"):
            return data
        return {
            "display_name": data.get("display_name", "unknown"),  # type: ignore[union-attr]
            "lat": float(lat),
            "lon": float(lon),
        }

    # -----------------------------
    # 3) Routing using OSRM API
    # -----------------------------
    def route(self, origin: Any, destination: Any) -> Dict[str, Any]:
        orig = self._resolve(origin)
        dest = self._resolve(destination)
        if not orig or not dest:
            return {"error": "Could not resolve origin or destination."}

        url = f"{self.p.osrm_route_url}/{orig['lon']},{orig['lat']};{dest['lon']},{dest['lat']}"
        params = {"overview": "false"}
        data = self._request_json(url, params=params)
        if isinstance(data, dict) and data.get("error"):
            return data
        if not data.get("routes"):
            return {"error": "No route found."}
        route = data["routes"][0]
        return {
            "distance_km": round(route["distance"] / 1000.0, 3),
            "duration_min": round(route["duration"] / 60.0, 1)
        }

    # -------------------------------------------
    # 4) Distance/Time Matrix via OSRM Table (new)
    # -------------------------------------------
    def matrix(self, places: List[Any]) -> Dict[str, Any]:
        """Return travel time (s) and distance (m) matrix for given places.
        Accepts strings (geocode), (lat, lon) tuples, or {lat, lon} dicts.
        """
        coords: List[Dict[str, float]] = []
        for p in places:
            r = self._resolve(p)
            if not r:
                return {"error": f"Could not resolve place: {p!r}"}
            coords.append(r)
        coord_str = ";".join(f"{c['lon']},{c['lat']}" for c in coords)
        url = f"{self.p.osrm_table_url}/{coord_str}"
        data = self._request_json(url)
        if isinstance(data, dict) and data.get("error"):
            return data
        if not data or "durations" not in data:
            return {"error": "No matrix returned."}
        return {
            "durations_s": data["durations"],
            "distances_m": data.get("distances"),  # may be absent on some OSRM deployments
        }

    # -------------------------------------------
    # 5) Optional: Overpass wrapper with endpoint fallback
    # -------------------------------------------
    def overpass(self, query: str) -> Dict[str, Any]:
        last_err: Optional[str] = None
        for ep in self.p.overpass_endpoints:
            resp = self._request_json(ep, params=None, data=query)
            if isinstance(resp, dict) and resp.get("error"):
                last_err = resp["error"]
                continue
            return {"elements": resp.get("elements", [])}  # type: ignore[union-attr]
        return {"error": last_err or "All Overpass endpoints failed"}

