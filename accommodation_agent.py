"""Voyage:One — Accommodation Agent: hotel search via Amadeus Hotels + offers."""
import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import time
import requests
from uagents import Agent, Context

from common import config
from common.models import HotelQuery, HotelOption, HotelResult

hotel = Agent(name="voyage_one_hotels", seed="voyage_one_hotel_seed",
              port=8003, endpoint=["http://localhost:8003/submit"])


def _token():
    r = requests.post(f"{config.AMADEUS_HOST}/v1/security/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": config.AMADEUS_CLIENT_ID,
        "client_secret": config.AMADEUS_CLIENT_SECRET}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def search_hotels(q: HotelQuery):
    token = _token()
    # 1) find hotels in city
    r = requests.get(f"{config.AMADEUS_HOST}/v1/reference-data/locations/hotels/by-city",
                     headers={"Authorization": f"Bearer {token}"},
                     params={"cityCode": q.city_code}, timeout=20)
    r.raise_for_status()
    hotels = r.json().get("data", [])[:10]

    # 2) get offers for those hotels
    ids = ",".join(h["hotelId"] for h in hotels)
    r2 = requests.get(f"{config.AMADEUS_HOST}/v3/shopping/hotel-offers",
                      headers={"Authorization": f"Bearer {token}"},
                      params={"hotelIds": ids, "checkInDate": q.check_in,
                              "checkOutDate": q.check_out, "adults": q.guests,
                              "currency": "USD"}, timeout=25)
    if r2.status_code != 200:
        return []
    out = []
    for offer in r2.json().get("data", []):
        h = offer.get("hotel", {})
        offers = offer.get("offers", [])
        if not offers:
            continue
        o = offers[0]
        price = float(o["price"].get("total", 0))
        if price > q.max_price_usd * 1.5:
            continue
        name = h.get("name", "Hotel")
        out.append({
            "hotel_id": h.get("hotelId", name),
            "name": name,
            "area": (h.get("address") or {}).get("cityName", ""),
            "rating": 4.2,
            "price_per_night_usd": price,
            "image_url": "",
            "total_price_usd": price,
            "amenities": [],
        })
        if len(out) >= 5:
            break
    return out


def fallback_hotels(q: HotelQuery):
    """Mock boutique/ryokan options so the demo works even if the test API quota
    is exhausted. Replace images with your own hosted URLs."""
    base = max(60.0, q.max_price_usd * 0.7)
    return [
        {"hotel_id": f"{q.city_code}-BK-1", "name": f"Boutique Sakura {q.city_code}",
         "area": "Old Town", "rating": 4.6, "price_per_night_usd": base,
         "image_url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600",
         "total_price_usd": base, "amenities": ["wifi", "spa"]},
        {"hotel_id": f"{q.city_code}-RY-2", "name": f"Ryokan Zen Garden {q.city_code}",
         "area": "Riverside", "rating": 4.8, "price_per_night_usd": base * 1.15,
         "image_url": "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?w=600",
         "total_price_usd": base * 1.15, "amenities": ["onsen", "kaiseki", "wifi"]},
        {"hotel_id": f"{q.city_code}-HT-3", "name": f"Grand {q.city_code} Palace",
         "area": "Downtown", "rating": 4.4, "price_per_night_usd": base * 0.85,
         "image_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600",
         "total_price_usd": base * 0.85, "amenities": ["wifi", "gym"]},
    ]


@hotel.on_message(model=HotelQuery)
async def on_query(ctx: Context, sender: str, q: HotelQuery):
    ctx.logger.info(f"Hotel query {q.city_code} {q.check_in}→{q.check_out} max ${q.max_price_usd}")
    options = []
    try:
        options = search_hotels(q)
    except Exception as e:
        ctx.logger.warning(f"Amadeus hotel search failed, using fallback: {e}")
    if not options:
        options = fallback_hotels(q)
    await ctx.send(sender, HotelResult(
        request_id=q.request_id,
        options=[HotelOption(**o) for o in options], error=""))


if __name__ == "__main__":
    hotel.run()
