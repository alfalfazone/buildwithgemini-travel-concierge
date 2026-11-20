# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google import genai
from google.genai import types

# Hardcoded project ID and public Cloud Storage bucket name as strings
PROJECT_ID = "qwiklabs-gcp-04-a2ba5fa4df78"
BUCKET_NAME = "travel-concierge-qwiklabs-gcp-04-a2ba5fa4df78"
AGENT_ENGINE_ID = "projects/173661590366/locations/us-east1/reasoningEngines/8949416620166479872"
MODEL = "gemini-3.8-flash"

# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)
destinations_ref = db.collection("travel_destinations")


def search_destinations(
    city: Optional[str] = None,
    country: Optional[str] = None,
    tag: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search travel destinations and hidden gems in the Firestore database.

    Args:
        city: Optional city filter (case-insensitive substring match).
        country: Optional country filter (case-insensitive substring match).
        tag: Optional tag filter (e.g. 'nature', 'hiking', 'culture', 'cafe', 'quiet').
        max_budget_usd: Optional maximum estimated cost filter in USD.

    Returns:
        A list of destination dictionaries matching the query criteria.
    """
    docs = destinations_ref.stream()
    results = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if city and city.lower() not in data.get("city", "").lower():
            continue
        if country and country.lower() not in data.get("country", "").lower():
            continue
        if tag and tag.lower() not in [t.lower() for t in data.get("tags", [])]:
            continue
        if max_budget_usd is not None and data.get("estimated_cost_usd", 0) > max_budget_usd:
            continue

        results.append(data)

    return results


def get_destination_details(destination_id: str) -> Dict[str, Any]:
    """Retrieve full details for a specific travel destination by its ID.

    Args:
        destination_id: The unique document ID (e.g. 'kyoto-arashiyama-bamboo', 'taipei-pingxi-valley').

    Returns:
        The destination detail dictionary, or an error status if not found.
    """
    doc = destinations_ref.document(destination_id).get()
    if not doc.exists:
        return {"error": f"Destination '{destination_id}' not found."}
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def add_custom_destination(
    destination_id: str,
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    tags: List[str],
    estimated_cost_usd: float = 0.0,
    recommended_pace: str = "moderate",
    best_time_to_visit: str = "Anytime",
) -> Dict[str, Any]:
    """Save a new travel destination or user-discovered secret spot into Firestore.

    Args:
        destination_id: A unique slug identifier for the spot (e.g. 'jiufen-tea-house').
        name: Name of the destination / spot.
        city: City where it is located.
        country: Country where it is located.
        category: Category (e.g. 'Hidden Nature', 'Local Food & Cafe', 'Historic Alley').
        description: A short engaging description of why it is special.
        tags: List of keywords/tags (e.g. ['tea', 'mountain', 'sunset']).
        estimated_cost_usd: Estimated budget / entrance cost in USD.
        recommended_pace: Recommended pace ('slow', 'moderate', 'fast').
        best_time_to_visit: Recommended time of day or season.

    Returns:
        Confirmation status and the saved destination item.
    """
    item = {
        "id": destination_id,
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "description": description,
        "tags": tags,
        "estimated_cost_usd": float(estimated_cost_usd),
        "recommended_pace": recommended_pace,
        "best_time_to_visit": best_time_to_visit,
        "rating": 5.0,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    destinations_ref.document(destination_id).set(item)
    return {"status": "success", "message": f"Saved destination '{name}' ({destination_id})", "destination": item}


def get_weather(city: str) -> Dict[str, Any]:
    """Fetch real-time current weather and temperature for any travel destination using the Open-Meteo public API.

    Args:
        city: City name to look up weather for (e.g. 'Kyoto', 'Taipei', 'Rome', 'Reykjavik', 'Bangkok').

    Returns:
        A dictionary with live weather conditions, temperature in Celsius, apparent feel, humidity, and wind speed.
    """
    import json
    import urllib.parse
    import urllib.request

    try:
        # Step 1: Geocode city name to latitude/longitude
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        if not geo_data.get("results"):
            return {"error": f"Could not find coordinates for city: {city}"}

        result = geo_data["results"][0]
        lat, lon = result["latitude"], result["longitude"]
        resolved_name = f"{result.get('name')}, {result.get('country', '')}"

        # Step 2: Fetch current weather metrics
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        )
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            w_data = json.loads(resp_w.read().decode("utf-8"))

        current = w_data.get("current", {})
        code = current.get("weather_code", 0)

        # Map WMO weather codes to descriptive text
        weather_conditions = {
            0: "晴朗無雲 (Clear sky)",
            1: "大部分晴朗 (Mainly clear)",
            2: "局部多雲 (Partly cloudy)",
            3: "多雲陰天 (Overcast)",
            45: "有霧 (Foggy)",
            48: "結霜霧 (Depositing rime fog)",
            51: "輕微細雨 (Light drizzle)",
            61: "微雨 (Slight rain)",
            63: "中雨 (Moderate rain)",
            65: "大雨 (Heavy rain)",
            71: "輕微降雪 (Slight snow fall)",
            80: "陣雨 (Rain showers)",
            95: "雷陣雨 (Thunderstorm)",
        }
        condition_desc = weather_conditions.get(code, "多雲或局部天氣變化")

        return {
            "city": resolved_name,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "condition": condition_desc,
        }
    except Exception as e:
        return {"error": f"Failed to retrieve weather for {city}: {str(e)}"}


def save_trip_itinerary(
    title: str,
    city: str,
    days: int,
    activities: List[str],
    notes: str = "",
) -> Dict[str, Any]:
    """Save a planned trip itinerary into the Firestore database.

    Args:
        title: Title of the itinerary (e.g. '京都秋季禪風散策 2 日遊').
        city: Primary destination city (e.g. 'Kyoto').
        days: Number of days for the trip.
        activities: Ordered list of activities/stops (e.g. ['08:00 嵐山竹林', '10:30 常寂光寺']).
        notes: Helpful tips or notes for the traveler.

    Returns:
        Confirmation dictionary containing status, itinerary ID, and saved details.
    """
    itinerary_id = f"trip-{city.lower().replace(' ', '-')}-{int(datetime.datetime.now().timestamp())}"
    data = {
        "id": itinerary_id,
        "title": title,
        "city": city,
        "days": days,
        "activities": activities,
        "notes": notes,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    db.collection("user_itineraries").document(itinerary_id).set(data)
    return {
        "status": "success",
        "message": f"Itinerary '{title}' successfully saved with ID: {itinerary_id}",
        "itinerary": data,
    }


def geocode_address(address: str) -> Dict[str, Any]:
    """Convert an address, landmark, or location name into geographic coordinates (latitude and longitude) using the Google Maps Geocoding API.

    Args:
        address: The street address or landmark to geocode (e.g. 'Kyoto Station', '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary containing the formatted address, location coordinates (lat, lng), place ID, or an error message.
    """
    import json
    import urllib.parse
    import urllib.request

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Geocoding failed for '{address}': {data.get('status')}"}

        res = data["results"][0]
        loc = res.get("geometry", {}).get("location", {})
        return {
            "name": address,
            "address": res.get("formatted_address"),
            "location": {
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
            },
            "place_id": res.get("place_id"),
        }
    except Exception as e:
        return {"error": f"Failed to geocode address '{address}': {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 1000.0,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """Find nearby places of a given type around specific geographic coordinates using the Google Maps Places API (New).

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g. 'restaurant', 'cafe', 'tourist_attraction', 'museum', 'park', 'bakery', 'lodging').
        radius_meters: Search radius in meters (default 1000m, max 50000m).
        max_results: Maximum number of places to return (default 5, max 20).

    Returns:
        A list of nearby places with their name, formatted address, and location coordinates.
    """
    import json
    import urllib.request

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}]

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.primaryType",
        }
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": min(max(1, max_results), 20),
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    },
                    "radius": float(radius_meters),
                }
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        places = data.get("places", [])
        results = []
        for p in places:
            results.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", "No address available"),
                "location": p.get("location", {}),
                "type": p.get("primaryType", place_type),
            })

        return results
    except Exception as e:
        return [{"error": f"Failed to search nearby places: {str(e)}"}]


async def generate_destination_image(
    prompt: str,
    tool_context: ToolContext,
    destination_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an aesthetic postcard-style preview image for a travel destination, secret spot, or scenic attraction.

    The generated image is:
    1. Saved as an ADK artifact via tool_context.save_artifact so it displays in the Playground's Artifacts panel.
    2. Uploaded directly to the project's public Cloud Storage bucket, returning its public HTTPS URL.

    Args:
        prompt: Descriptive scene prompt for image generation (e.g. 'A serene Kyoto bamboo grove bathed in soft morning mist, cinematic photorealistic lighting').
        tool_context: ADK ToolContext used to save the image as a conversation artifact.
        destination_name: Optional short name/slug of the destination for file naming (e.g. 'kyoto_bamboo').

    Returns:
        A dictionary containing the public image URL, artifact filename, and status.
    """
    slug = (destination_name or "destination").lower().replace(" ", "_")
    timestamp = int(datetime.datetime.now().timestamp())
    filename = f"{slug}_{timestamp}.jpeg"

    try:
        # Initialize Google GenAI client targeting the global region
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
            http_options=types.HttpOptions(api_version="v1"),
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return {"error": "No image data was generated by the model."}

        # 1. Save artifact to Playground's Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        artifact_version = await tool_context.save_artifact(
            filename=filename,
            artifact=artifact_part,
        )

        # 2. Upload to public Cloud Storage bucket without writing to local disk
        gcs_client = storage.Client(project=PROJECT_ID)
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "message": f"Successfully generated postcard image for '{destination_name or prompt}'",
            "public_url": public_url,
            "artifact_filename": filename,
            "artifact_version": artifact_version,
        }
    except Exception as e:
        return {"error": f"Failed to generate destination image: {str(e)}"}


async def generate_destination_video(
    prompt: str,
    tool_context: ToolContext,
    destination_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a short cinematic preview video for a travel destination, secret spot, or scenic attraction using Google's Omni model (gemini-omni-flash-preview) in the global region.

    The generated video is:
    1. Saved as an ADK artifact via tool_context.save_artifact so it displays in the Playground's Artifacts panel.
    2. Uploaded directly to the project's public Cloud Storage bucket, returning its public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>).

    Args:
        prompt: Descriptive scene prompt for video generation (e.g. 'A 3-second cinematic flyover of a tranquil Japanese bamboo forest in morning mist, smooth continuous drone shot.').
        tool_context: ADK ToolContext used to save the video as a conversation artifact.
        destination_name: Optional short name/slug of the destination for file naming (e.g. 'kyoto_bamboo').

    Returns:
        A dictionary containing the public video URL, artifact filename, and status.
    """
    import base64

    slug = (destination_name or "destination").lower().replace(" ", "_")
    timestamp = int(datetime.datetime.now().timestamp())
    filename = f"{slug}_{timestamp}.mp4"

    try:
        # Initialize Google GenAI client targeting the global region
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )

        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"

        output_video = getattr(interaction, "output_video", None)
        if output_video and getattr(output_video, "data", None):
            mime_type = getattr(output_video, "mime_type", "video/mp4") or "video/mp4"
            raw_data = output_video.data
            if isinstance(raw_data, str):
                video_bytes = base64.b64decode(raw_data)
            else:
                video_bytes = raw_data

        if not video_bytes:
            return {"error": "No video data was generated by the model."}

        # 1. Save artifact to Playground's Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        artifact_version = await tool_context.save_artifact(
            filename=filename,
            artifact=artifact_part,
        )

        # 2. Upload to public Cloud Storage bucket without writing to local disk
        gcs_client = storage.Client(project=PROJECT_ID)
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "message": f"Successfully generated short video for '{destination_name or prompt}'",
            "public_url": public_url,
            "artifact_filename": filename,
            "artifact_version": artifact_version,
        }
    except Exception as e:
        return {"error": f"Failed to generate destination video: {str(e)}"}


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and travel preferences into Vertex AI Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are the Travel Concierge (智慧旅遊與秘境規劃師), a helpful and knowledgeable travel planning assistant. "
        "You strictly remember and track all user allergies (e.g., seafood, peanuts, gluten, dairy, medication allergies, etc.), "
        "dietary restrictions, travel preferences, favorite styles, budget limits, and past conversation facts across sessions. "
        "Always cross-reference and respect the traveler's remembered allergies and dietary restrictions when recommending restaurants, "
        "dining spots, culinary experiences, or planning itinerary meals. "
        "You help travelers explore curated destinations and secret spots stored in Firestore, plan tailor-made itineraries, "
        "query live weather forecasts, geocode addresses, find nearby places using Google Maps, generate scenic postcard images, "
        "generate short destination preview videos, "
        "and perform complex calculations or data analysis using Python code execution in a secure sandbox. "
        "When travelers ask for budget calculations, currency conversions, route time sums, or custom statistics, write and execute Python code in the sandbox. "
        "When travelers ask for recommendations or destinations, use search_destinations or get_destination_details. "
        "When travelers ask for a picture, postcard, visual preview, or photo of a destination or attraction, use generate_destination_image. "
        "When travelers ask for a video, short clip, or animated preview of a destination or attraction, use generate_destination_video. "
        "When travelers provide an address or landmark, use geocode_address to find its coordinates. "
        "When travelers want to discover nearby dining, cafes, attractions, or hotels around coordinates, use find_nearby_places. "
        "When a traveler wants to save or finalize a planned itinerary, use save_trip_itinerary to store it in Firestore. "
        "If they share a new secret spot they loved, use add_custom_destination to store it. "
        "Respond in traditional Chinese (繁體中文) by default unless requested otherwise."
    ),
    workflow_description="Analyze the request, call relevant tools to gather data or take actions, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        client_kwargs={
            "vertexai": True,
            "project": PROJECT_ID,
            "location": "global",
        },
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=AgentEngineSandboxCodeExecutor(
        sandbox_resource_name="projects/173661590366/locations/us-east1/reasoningEngines/8949416620166479872/sandboxEnvironments/375349080466915328",
        agent_engine_resource_name=AGENT_ENGINE_ID,
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_custom_destination,
        save_trip_itinerary,
        get_weather,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
