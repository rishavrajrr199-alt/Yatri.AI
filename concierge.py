"""
Voyage:One — Concierge Agent (main router).

Register this agent on Agentverse and connect it to ASI:One.
Workflow:
 1. Parse user's vague travel intent (LLM, with regex fallback)
 2. -> Itinerary Planner Agent
 3. -> Transport & Accommodation agents (parallel)
 4. Carousel of hotels -> user picks
 5. Form for traveler details -> user submits
 6. -> Transaction Agent (payment authorization, $5 fee)
 7. Final detail card with confirmations
 8. If a leg is sold out -> autonomous replan loop with planner
"""
import asyncio
import re
import json
import uuid
from datetime import datetime, timedelta

from datetime import datetime, timedelta, timezone
from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from common import config
from common.models import (
    TripIntent, Itinerary, TransportQuery, TransportResult,
    HotelQuery, HotelResult, BookingRequest, BookingConfirmation,
    PaymentRequest, PaymentAuthorization, ReplanRequest,
)
from common.cards import (
    hotel_carousel, traveler_form, payment_card,
    itinerary_detail_card, render, parse_user_card_response,
)

chat_proto = Protocol(spec=chat_protocol_spec)
asyncio.set_event_loop(asyncio.new_event_loop())
concierge = Agent(
    name="voyage_one_concierge",
    seed=config.PLANNER_ADDR and None or "voyage_one_concierge_seed",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
)



# ---------------- Intent parsing ----------------
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def fallback_parse(text: str) -> dict:
    """Regex/dateutil-free heuristic parser used when no OpenAI key is set."""
    dest = None
    for city in ["Paris", "Kyoto", "Tokyo", "London", "Rome", "Barcelona", "New York"]:
        if city.lower() in text.lower():
            dest = city
            break
    dates = DATE_RE.findall(text)
    start = dates[0] if dates else (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    end = dates[1] if len(dates) > 1 else (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=3)).strftime("%Y-%m-%d")
    m = re.search(r"\$(\d+)", text)
    budget = float(m.group(1)) if m else 1500.0
    return {"destination": dest or "Paris", "origin": "London",
            "start_date": start, "end_date": end, "budget": budget,
            "style": "romantic" if "romantic" in text.lower() else "any"}


async def parse_intent(ctx: Context, text: str) -> TripIntent:
    parsed = None
    if config.OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content":
                     "Extract travel intent as JSON: destination, origin, start_date (YYYY-MM-DD, "
                     "resolve relative dates from today), end_date, budget_total_usd, trip_style. Today is "
                     + datetime.now().strftime("%Y-%m-%d")},
                    {"role": "user", "content": text},
                ],
            )
            parsed = json.loads(resp.choices[0].message.content)
        except Exception as e:
            ctx.logger.warning(f"LLM parse failed, using fallback: {e}")
    if not parsed:
        parsed = fallback_parse(text)
    return TripIntent(
        request_id=str(uuid.uuid4())[:8],
        destination=parsed["destination"],
        origin=parsed.get("origin", "London"),
        start_date=parsed["start_date"],
        end_date=parsed["end_date"],
        budget_total_usd=float(parsed.get("budget", parsed.get("budget_total_usd", 1500))),
        trip_style=parsed.get("style", parsed.get("trip_style", "any")),
        notes=text,
    )


# ---------------- Conversation state ----------------
SESSIONS: dict = {}   # request_id -> session dict


async def send(ctx, addr, model: Model):
    if not addr:
        ctx.logger.error("Agent address missing! Fill common/config.py with registered addresses.")
        return
    await ctx.send(addr, model)


# ---------------- ASI:One chat entry ----------------

@chat_proto.on_message(ChatMessage)
async def on_user_message(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge the incoming chat message.
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Extract readable text from the chat message.
    text = "\n".join(
        item.text
        for item in msg.content
        if isinstance(item, TextContent)
    ).strip()

    if not text:
        ctx.logger.warning("Received a chat message without text content.")
        return

    if any(
        action in text
        for action in (
            "select_hotel",
            "submit_traveler",
            "authorize_payment",
        )
    ):
        await handle_card_response(ctx, sender, text)
        return

    if "replan" not in text.lower() and any(
        session.get("phase") == "awaiting_payment"
        for session in SESSIONS.values()
    ):
        pass

    ctx.logger.info(f"New intent: {text}")
    intent = await parse_intent(ctx, text)

    SESSIONS[intent.request_id] = {
        "phase": "planning",
        "sender": sender,
        "intent": intent,
    }

    await ctx.send(
        sender,
        f"Planning your trip to {intent.destination} "
        f"({intent.start_date} -> {intent.end_date}). "
        "Coordinating with the itinerary, transport and hotel agents."
    )

    await send(ctx, config.PLANNER_ADDR, intent)


# ---------------- Itinerary in, inventory out ----------------
@concierge.on_message(model=Itinerary)
async def on_itinerary(ctx: Context, sender: str, itin: Itinerary):
    s = SESSIONS.get(itin.request_id)
    if not s:
        return
    s["itinerary"] = itin
    intent: TripIntent = s["intent"]
    nights = max(1, (datetime.strptime(intent.end_date, "%Y-%m-%d")
                     - datetime.strptime(intent.start_date, "%Y-%m-%d")).days)
    s["nights"] = nights

    plan_lines = "\n".join(f"Day {d.day} ({d.date}): {d.summary}" for d in itin.days)
    await ctx.send(s["sender"], f"📋 Itinerary ready:\n{plan_lines}\n\n"
                                f"🔍 Searching real-time transport and hotels…")

    # Kick off both searches in parallel
    hq = HotelQuery(
        request_id=itin.request_id,
        city_code=_city_code(intent.destination),
        check_in=intent.start_date, check_out=intent.end_date,
        max_price_usd=intent.budget_total_usd / max(nights, 1),
        vibe=intent.trip_style,
    )
    await send(ctx, config.HOTEL_ADDR, hq)

    tqs = []
    for d in itin.days:
        if d.transport_pref and d.transport_pref != "any":
            tqs.append(TransportQuery(
                request_id=itin.request_id,
                origin_iata=_city_code(s["intent"].origin),
                destination_iata=_city_code(s["intent"].destination),
                date=d.date, mode=d.transport_pref))
    if not tqs:  # default: outbound on first day, return on last
        tqs = [TransportQuery(request_id=itin.request_id,
                              origin_iata=_city_code(intent.origin),
                              destination_iata=_city_code(intent.destination),
                              date=intent.start_date, mode="any")]
        tqs.append(TransportQuery(request_id=itin.request_id,
                                  origin_iata=_city_code(intent.destination),
                                  destination_iata=_city_code(intent.origin),
                                  date=intent.end_date, mode="any"))
    s["transport_results"] = []
    s["expected_transport"] = len(tqs)
    for tq in tqs:
        await send(ctx, config.TRANSPORT_ADDR, tq)


def _city_code(city: str) -> str:
    known = {"Paris": "PAR", "London": "LON", "Kyoto": "UKY", "Tokyo": "TYO",
             "Rome": "ROM", "Barcelona": "BCN", "New York": "NYC"}
    return known.get(city, city[:3].upper())


@concierge.on_message(model=HotelResult)
async def on_hotels(ctx: Context, sender: str, res: HotelResult):
    s = SESSIONS.get(res.request_id)
    if not s:
        return
    if res.error or not res.options:
        await ctx.send(s["sender"], f"⚠️ No hotels found ({res.error or 'no availability'}). Adjusting budget and retrying…")
        hq = HotelQuery(request_id=res.request_id, city_code=_city_code(s["intent"].destination),
                        check_in=s["intent"].start_date, check_out=s["intent"].end_date,
                        max_price_usd=s["intent"].budget_total_usd / max(s.get("nights", 1), 1) * 1.5,
                        vibe=s["intent"].trip_style)
        await send(ctx, config.HOTEL_ADDR, hq)
        return
    s["hotels"] = res.options
    s["phase"] = "awaiting_hotel_pick"
    await ctx.send(s["sender"], "🏨 Here are hotel options matching your vibe:",
                   **{})  # payload below carries the card
    await ctx.send(s["sender"], json.dumps({"asi1_card": hotel_carousel(res.options)}))


@concierge.on_message(model=TransportResult)
async def on_transport(ctx: Context, sender: str, res: TransportResult):
    s = SESSIONS.get(res.request_id)
    if not s:
        return
    if res.error or all(o.sold_out for o in res.options):
        ctx.logger.warning(f"Leg failed: {res.error}. Triggering autonomous replan.")
        await ctx.send(s["sender"], f"⚠️ Requested transport is sold out ({res.error or 'sold out'}). "
                                    f"Asking my Itinerary Planner to rework the schedule…")
        await send(ctx, config.PLANNER_ADDR, ReplanRequest(
            request_id=res.request_id, reason="transport_sold_out",
            failed_leg=res.options[0].destination if res.options else "unknown"))
        return
    s.setdefault("transport_results", []).append(res)
    if len(s["transport_results"]) >= s.get("expected_transport", 1) and s.get("phase") == "awaiting_hotel_pick":
        await maybe_show_booking_review(ctx, s)


async def maybe_show_booking_review(ctx: Context, s: dict):
    """Once hotels + all transport legs are in, show summary and form."""
    if not s.get("hotels"):
        return
    options = []
    for tr in s["transport_results"]:
        options.extend([o for o in tr.options if not o.sold_out])
    s["phase"] = "awaiting_traveler_form"
    total_est = sum(h.price_per_night_usd * s.get("nights", 1) for h in s["hotels"][:1]) \
        + sum(o.price_usd for o in options)
    s["pending_total"] = total_est
    await ctx.send(s["sender"], "✈️ Transport secured. Please confirm traveler details to lock everything in:")
    await ctx.send(s["sender"], json.dumps({"asi1_card": traveler_form()}))


# ---------------- Card responses ----------------
async def handle_card_response(ctx: Context, sender: str, text: str):
    data = parse_user_card_response(text)
    for rid, s in SESSIONS.items():
        if s["sender"] != sender:
            continue
        if data.get("action") == "select_hotel" or "hotel_id" in data:
            s["chosen_hotel"] = next((h for h in s.get("hotels", [])
                                      if h.hotel_id == data.get("hotel_id")), s["hotels"][0])
            await ctx.send(sender, f"Great choice — {s['chosen_hotel'].name}. "
                                   "Please confirm your travel details to lock in transport:")
            await ctx.send(sender, json.dumps({"asi1_card": traveler_form()}))
            s["phase"] = "awaiting_traveler_form"
            return
        if data.get("action") == "submit_traveler":
            br = BookingRequest(
                request_id=rid,
                traveler_name=data.get("traveler_name", "Traveler"),
                traveler_dob=data.get("traveler_dob", "1990-01-01"),
                passport_number=data.get("passport_number", ""),
                hotel=s["chosen_hotel"],
                transport=[o for tr in s["transport_results"] for o in tr.options if not o.sold_out],
            )
            s["phase"] = "awaiting_payment"
            await send(ctx, config.TXN_ADDR, br)
            return
        if data.get("action") == "authorize_payment" or "authorized" in data:
            s["authorized"] = True
            await send(ctx, config.TXN_ADDR, PaymentAuthorization(
                request_id=rid, authorized=True, user_message="user authorized in chat"))
            return


# ---------------- Payment + completion ----------------
@concierge.on_message(model=PaymentRequest)
async def on_payment_request(ctx: Context, sender: str, pr: PaymentRequest):
    s = SESSIONS.get(pr.request_id)
    if not s:
        return
    await ctx.send(s["sender"], "💳 Your trip is ready. Please authorize payment:")
    await ctx.send(s["sender"], json.dumps({"asi1_card": payment_card(pr.total_usd, pr.fee_usd, pr.summary)}))


@concierge.on_message(model=BookingConfirmation)
async def on_confirmation(ctx: Context, sender: str, conf: BookingConfirmation):
    s = SESSIONS.get(conf.request_id)
    if not s:
        return
    if conf.error:
        await ctx.send(s["sender"], f"❌ Booking failed: {conf.error}. Let's try alternatives.")
        return
    plan = s.get("itinerary")
    plan_text = "\n".join(f"Day {d.day} ({d.date}): {d.summary}" for d in plan.days) if plan else "Itinerary attached."
    await ctx.send(s["sender"], "🎉 Trip confirmed!")
    await ctx.send(s["sender"], json.dumps({"asi1_card": itinerary_detail_card(conf, plan_text)}))
    SESSIONS.pop(conf.request_id, None)


@concierge.on_message(model=Itinerary)  # replanned itineraries also arrive here
async def _noop(ctx, sender, itin):
    pass


if __name__ == "__main__":
    concierge.run()
