# ==========================
# File: assistant_agent.py
# ==========================

from __future__ import annotations
import os
from typing import Any, Dict, List
from openai import OpenAI

from dummy_map_server import DummyMapServer
from openstreetmap_server import OpenStreetMapServer


# ==========================
# MAP TOOL WRAPPERS
# ==========================

class DummyMapTool:
    def __init__(self):
        self.server = DummyMapServer()

    def geocode(self, query: str):
        return self.server.geocode(query)

    def route(self, origin: str, destination: str):
        return self.server.route(origin, destination)

    def poi(self, query: str, near: str):
        return self.server.search_poi(query, near)


class OpenStreetMapTool:
    def __init__(self):
        self.server = OpenStreetMapServer()

    def geocode(self, query: str):
        return self.server.geocode(query)

    def reverse_geocode(self, lat: float, lon: float):
        return self.server.reverse_geocode(lat, lon)

    def route(self, origin: str, destination: str):
        return self.server.route(origin, destination)

    def matrix(self, places: List[str]):
        return self.server.matrix(places)


# ==========================
# ASSISTANT AGENT (FUNCTION CALLING)
# ==========================

class AssistantAgent:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model

        self.dummy = DummyMapTool()
        self.osm = OpenStreetMapTool()

        self.last_call: Dict[str, Any] | None = None

        # **The function definitions**
        self.functions = [
            {
                "name": "dummy_geocode",
                "description": "Local dummy geocoding.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "dummy_route",
                "description": "Local dummy routing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "dummy_poi",
                "description": "Local POI search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "near": {"type": "string"},
                    },
                    "required": ["query", "near"],
                },
            },
            {
                "name": "osm_geocode",
                "description": "Real OpenStreetMap geocoding.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "osm_reverse_geocode",
                "description": "Reverse geocode lat/lon.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                    },
                    "required": ["lat", "lon"],
                },
            },
            {
                "name": "osm_route",
                "description": "OSM routing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "osm_matrix",
                "description": "Matrix distances/times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "places": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["places"],
                },
            },
        ]

    # ==========================
    # RUN USER MESSAGE THROUGH LLM
    # ==========================

    def interpret(self, message: str):
        """Send user message → model → get function call"""

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a mapping assistant. ALWAYS use one of the "
                        "provided functions. Never output text yourself."
                    ),
                },
                {"role": "user", "content": message},
            ],
            functions=self.functions,
            function_call="auto",
        )

        msg = completion.choices[0].message

        if msg.function_call is None:
            return {"error": "LLM did not choose a function"}

        # store for 'again'
        self.last_call = msg.function_call

        return msg.function_call

    # ==========================
    # EXECUTE FUNCTION CALL
    # ==========================

    def execute(self, fn) -> Any:
        name = fn.name
        args = fn.arguments

        # Dummy tool
        if name == "dummy_geocode":
            return self.dummy.geocode(args["query"])

        if name == "dummy_route":
            return self.dummy.route(args["origin"], args["destination"])

        if name == "dummy_poi":
            return self.dummy.poi(args["query"], args["near"])

        # OSM tool
        if name == "osm_geocode":
            return self.osm.geocode(args["query"])

        if name == "osm_reverse_geocode":
            return self.osm.reverse_geocode(args["lat"], args["lon"])

        if name == "osm_route":
            return self.osm.route(args["origin"], args["destination"])

        if name == "osm_matrix":
            return self.osm.matrix(args["places"])

        return {"error": f"Unknown function '{name}'"}

    # ==========================
    # MAIN LOOP
    # ==========================

    def run(self):
        print("🌍 OpenAI Smart Map Assistant (Function Calling) ready.\n")

        while True:
            msg = input("You: ")
            if msg.lower() in ("quit", "exit"):
                break
            if msg.lower() in ("again", "repeat") and self.last_call:
                fn = self.last_call
                result = self.execute(fn)
                print("🧭 Result:", result)
                continue

            fn = self.interpret(msg)
            if "error" in fn:
                print("⚠️ Error:", fn["error"])
                continue

            result = self.execute(fn)
            print("🧭 Result:", result)
            print()
