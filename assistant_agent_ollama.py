# ==========================
# File: assistant.py
# ==========================
from __future__ import annotations
import json, re
from typing import Any, Dict

from ollama_client import OllamaClient
from dummy_map_server import DummyMapServer
from openstreetmap_server import OpenStreetMapServer


# ==========================
# MAP TOOLS
# ==========================

class MapTool:
    name: str
    description: str
    def run(self, **kwargs) -> Any:
        raise NotImplementedError


class DummyMapTool(MapTool):
    name = "dummy"
    description = "Local dummy POI server."

    def __init__(self):
        self.server = DummyMapServer()

    def run(self, action: str, **kwargs):
        try:
            if action == "geocode":
                return self.server.geocode(kwargs.get("query"))

            elif action == "route":
                return self.server.route(kwargs.get("origin"), kwargs.get("destination"))

            elif action == "poi":
                res = self.server.search_poi(kwargs.get("query"), kwargs.get("near"))
                return res if res else {"message": "No places found matching your search."}

            else:
                return {"error": f"Unknown action: {action}"}

        except Exception as e:
            return {"error": str(e)}


class OpenStreetMapTool(MapTool):
    name = "osm"
    description = "OpenStreetMap API wrapper."

    def __init__(self):
        self.server = OpenStreetMapServer()

    def run(self, action: str, **kwargs):
        try:
            if action == "geocode":
                return self.server.geocode(kwargs.get("query"))

            elif action == "reverse_geocode":
                return self.server.reverse_geocode(float(kwargs["lat"]),
                                                   float(kwargs["lon"]))

            elif action == "route":
                return self.server.route(kwargs.get("origin"),
                                         kwargs.get("destination"))

            elif action == "matrix":
                places = kwargs.get("places")
                if not places:
                    return {"error": "Matrix requires a list of places."}
                return self.server.matrix(places)

            else:
                return {"error": f"Unsupported action: {action}"}

        except Exception as e:
            return {"error": str(e)}


# ==========================
# ASSISTANT AGENT
# ==========================

class AssistantAgent:
    def __init__(self, model: str | None = None):
        self.client = OllamaClient(model or "llama3:8b")
        self.tools = {
            "dummy": DummyMapTool(),
            "osm": OpenStreetMapTool()
        }
        self.last_plan: Dict[str, Any] | None = None


    # ---------- JSON Extraction ----------
    def _extract_json(self, text: str):
        try:
            return json.loads(text)
        except:
            pass

        blocks = re.findall(r"\{[\s\S]*?\}", text)
        for b in blocks:
            try:
                return json.loads(b)
            except:
                continue

        return None


    # ---------- INTERPRET USER ----------
    def interpret(self, message: str) -> Dict[str, Any]:

        raw = message.strip()
        lower = raw.lower()

        # ==============================
        #       HARD RULES
        # ==============================

        # WHERE IS <PLACE>
        m = re.match(r"where is (.+)", lower)
        if m:
            place = m.group(1).replace("located", "").strip()
            print(f"DEBUG — place extracted: {place}")
            return {"tool": "osm", "action": "geocode", "params": {"query": place}}

        # WHAT IS AT <LAT>, <LON>
        m = re.match(r"what is at ([0-9.\-]+)[ ,]+([0-9.\-]+)", lower)
        if m:
            return {
                "tool": "osm",
                "action": "reverse_geocode",
                "params": {"lat": m.group(1), "lon": m.group(2)}
            }

        # FIND X NEAR Y
        m = re.match(r"find (.+) near (.+)", lower)
        if m:
            return {
                "tool": "dummy",
                "action": "poi",
                "params": {"query": m.group(1).strip(), "near": m.group(2).strip()}
            }

        # ROUTE: from X to Y
        m = re.match(r"give me a route from (.+) to (.+)", lower)
        if m:
            return {
                "tool": "osm",
                "action": "route",
                "params": {"origin": m.group(1).strip(), "destination": m.group(2).strip()}
            }

        # TRAVEL MATRIX — extract list of places
        if "matrix" in lower:
            m = re.search(r"matrix (for )?(.*)", lower)
            if m:
                places_raw = m.group(2)
                places = [p.strip() for p in places_raw.split(",") if p.strip()]
                if places:
                    print(f"DEBUG — matrix extracted places: {places}")
                    return {"tool": "osm", "action": "matrix", "params": {"places": places}}
            return {"error": "Could not extract places for matrix."}

        # REPEAT LAST
        if lower in {"again", "repeat", "same"} and self.last_plan:
            return self.last_plan

        # ==============================
        #       FALLBACK TO LLM
        # ==============================

        system_prompt = (
            "Choose correct mapping tool.\n"
            "- dummy → POI searches like 'restaurants near X'\n"
            "- osm → geocode, reverse_geocode, route, matrix\n"
            "Return ONLY JSON."
        )

        llm_out = self.client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw}
        ])

        plan = self._extract_json(llm_out)
        if plan and "tool" in plan:
            self.last_plan = plan
            return plan

        return {"error": "Failed to interpret", "raw": llm_out}


    # ---------- RUN LOOP ----------
    def run(self):
        print("🌍 Smart Map Assistant (Ollama) ready. Type 'quit' to exit.\n")

        while True:
            msg = input("You: ")
            if msg.lower() in ["quit", "exit"]:
                break

            plan = self.interpret(msg)

            if "error" in plan:
                print("⚠️ Could not interpret:", plan.get("raw"))
                continue

            tool = self.tools.get(plan["tool"])
            result = tool.run(plan["action"], **plan["params"])

            print("🧭 Result:", result)
            print()


# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    AssistantAgent().run()
