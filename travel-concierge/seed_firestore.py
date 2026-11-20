#!/usr/bin/env python3
"""Seed script for travel-concierge destinations in Firestore."""

from google.cloud import firestore

# Hardcoded project ID as required
PROJECT_ID = "qwiklabs-gcp-04-a2ba5fa4df78"

SEEDED_DESTINATIONS = [
    {
        "id": "kyoto-arashiyama-bamboo",
        "name": "嵯峨野竹林與常寂光寺 (Arashiyama Bamboo Grove & Jojakko-ji)",
        "city": "Kyoto",
        "country": "Japan",
        "category": "Hidden Nature & Temples",
        "tags": ["nature", "quiet", "autumn", "culture", "photography"],
        "recommended_pace": "slow",
        "description": "遠離主街道喧囂的小徑，晨間漫步於參天竹林與寧靜的常寂光寺青苔庭園。",
        "best_time_to_visit": "07:00 - 09:00",
        "estimated_cost_usd": 15,
        "rating": 4.9
    },
    {
        "id": "taipei-pingxi-valley",
        "name": "望古瀑布與嶺腳秘境步道 (Wanggu Waterfall & Lingjiao)",
        "city": "New Taipei",
        "country": "Taiwan",
        "category": "Hidden Nature & Hiking",
        "tags": ["waterfall", "hiking", "nature", "peaceful", "railway"],
        "recommended_pace": "moderate",
        "description": "平溪線上的隱藏寶石，碧綠潭水如鏡，沿著靜謐鐵道與古樸嶺腳古橋漫步。",
        "best_time_to_visit": "09:00 - 12:00",
        "estimated_cost_usd": 10,
        "rating": 4.8
    },
    {
        "id": "rome-coppede-district",
        "name": "科佩德奇幻街區 (Quartiere Coppedè)",
        "city": "Rome",
        "country": "Italy",
        "category": "Hidden Architecture & Culture",
        "tags": ["architecture", "fairy-tale", "art-nouveau", "quiet", "photo-spot"],
        "recommended_pace": "slow",
        "description": "融合新藝術、哥德與巴洛克風格的童話般古老街區，鮮少遊客的羅馬祕密花園。",
        "best_time_to_visit": "15:00 - 18:00",
        "estimated_cost_usd": 0,
        "rating": 4.7
    },
    {
        "id": "iceland-fjadrargljufur-canyon",
        "name": "羽毛峽谷 (Fjaðrárgljúfur Canyon)",
        "city": "Kirkjubæjarklaustur",
        "country": "Iceland",
        "category": "Epic Scenery & Canyon",
        "tags": ["canyon", "hiking", "dramatic", "nature", "scenic"],
        "recommended_pace": "moderate",
        "description": "宛如巨龍蜿蜒的百米深苔蘚峽谷，擁有億萬年冰川沖刷出的奇幻地貌。",
        "best_time_to_visit": "10:00 - 16:00",
        "estimated_cost_usd": 20,
        "rating": 4.9
    },
    {
        "id": "bangkok-talat-noi-alley",
        "name": "沓叻仔老城區 (Talat Noi Heritage Alleys)",
        "city": "Bangkok",
        "country": "Thailand",
        "category": "Local Heritage & Cafe",
        "tags": ["street-art", "cafe", "vintage", "heritage", "food"],
        "recommended_pace": "slow",
        "description": "昭披耶河畔充滿生機的古老華人街區，鐵工廠與老屋文青咖啡館交織的迷人巷弄。",
        "best_time_to_visit": "14:00 - 19:00",
        "estimated_cost_usd": 25,
        "rating": 4.8
    }
]

def seed():
    print(f"Connecting to Firestore with project ID: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection("travel_destinations")
    
    for item in SEEDED_DESTINATIONS:
        doc_id = item["id"]
        collection.document(doc_id).set(item)
        print(f"  ✓ Seeded destination: {item['name']} ({doc_id})")
        
    print(f"\nSuccessfully seeded {len(SEEDED_DESTINATIONS)} destinations into 'travel_destinations' collection!")

if __name__ == "__main__":
    seed()
