from typing import List, Optional
from uagents import Model

class TripIntent(Model):
    request_id: str
    destination: str
    origin: str
    start_date: str
    end_date: str
    budget_total_usd: float = 1500
    trip_style: str = "any"
    notes: str = ""
    transport_pref_note: Optional[str] = None

class DayPlan(Model):
    day: int
    date: str
    summary: str
    transport_pref: str = "any"
    hotel_area_hint: str = "city center"

class Itinerary(Model):
    request_id: str
    days: List[DayPlan]
    est_lodging_budget_usd: float = 0
    est_transport_budget_usd: float = 0

class ReplanRequest(Model):
    request_id: str
    reason: str
    failed_leg: str = "unknown"
    constraints: dict = {}

class TransportQuery(Model):
    request_id: str
    origin_iata: str
    destination_iata: str
    date: str
    mode: str = "any"
    passengers: int = 1

class TransportOption(Model):
    option_id: str
    mode: str
    origin: str
    destination: str
    date: str
    departure: str
    arrival: str
    price_usd: float
    sold_out: bool = False
    provider: str = "Demo inventory"

class TransportResult(Model):
    request_id: str
    options: List[TransportOption]
    error: str = ""

class HotelQuery(Model):
    request_id: str
    city_code: str
    check_in: str
    check_out: str
    max_price_usd: float
    vibe: str = "any"
    guests: int = 1

class HotelOption(Model):
    hotel_id: str
    name: str
    area: str = ""
    rating: float = 4.5
    price_per_night_usd: float
    image_url: str = ""
    total_price_usd: float
    amenities: List[str] = []

class HotelResult(Model):
    request_id: str
    options: List[HotelOption]
    error: str = ""

class BookingRequest(Model):
    request_id: str
    traveler_name: str
    traveler_dob: str
    passport_number: str = ""
    hotel: HotelOption
    transport: List[TransportOption]

class PaymentRequest(Model):
    request_id: str
    total_usd: float
    fee_usd: float
    summary: str

class PaymentAuthorization(Model):
    request_id: str
    authorized: bool
    user_message: str = ""

class BookingConfirmation(Model):
    request_id: str
    hotel_confirmation: str = ""
    transport_confirmations: List[str] = []
    total_usd: float = 0
    fee_usd: float = 5
    payment_authorized: bool = False
    error: str = ""
