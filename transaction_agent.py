"""Voyage:One — Transaction Agent.
Handles the Payment Protocol: presents the payment request (via Concierge →
user), waits for authorization, finalizes bookings, returns confirmations.
Monetization: flat $5 orchestration fee (+ future affiliate commissions).
For the hackathon, payments are mocked; wire the Fetch.ai Payment Protocol
or a Stripe test key here for real authorization."""
import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import uuid
from uagents import Agent, Context

from common import config
from common.models import (
    BookingRequest, BookingConfirmation, PaymentRequest, PaymentAuthorization,
)

txn = Agent(name="voyage_one_txn", seed="voyage_one_txn_seed",
            port=8004, endpoint=["http://localhost:8004/submit"])

PENDING: dict = {}   # request_id -> BookingRequest


@txn.on_message(model=BookingRequest)
async def on_booking(ctx: Context, sender: str, br: BookingRequest):
    total = br.hotel.total_price_usd + sum(t.price_usd for t in br.transport)
    PENDING[br.request_id] = br
    summary = (f"{br.hotel.name} ({br.hotel.total_price_usd:.0f}/night) + "
               f"{len(br.transport)} transport leg(s) for {br.traveler_name}")
    await ctx.send(sender, PaymentRequest(
        request_id=br.request_id, total_usd=total,
        fee_usd=config.ORCHESTRATION_FEE_USD, summary=summary))


@txn.on_message(model=PaymentAuthorization)
async def on_auth(ctx: Context, sender: str, auth: PaymentAuthorization):
    br = PENDING.pop(auth.request_id, None)
    if not br:
        return
    if not auth.authorized:
        await ctx.send(sender, BookingConfirmation(
            request_id=auth.request_id, error="payment declined by user"))
        return
    # ---- Mock booking finalization (swap for Amadeus / Duffel booking calls) ----
    hotel_conf = f"HTL-{uuid.uuid4().hex[:8].upper()}"
    transport_confs = [f"{t.mode.upper()}-{uuid.uuid4().hex[:6].upper()}"
                       for t in br.transport]
    total = br.hotel.total_price_usd + sum(t.price_usd for t in br.transport)
    ctx.logger.info(f"Booked {auth.request_id}: {hotel_conf} + {len(transport_confs)} legs")
    await ctx.send(sender, BookingConfirmation(
        request_id=auth.request_id, hotel_confirmation=hotel_conf,
        transport_confirmations=transport_confs,
        total_usd=total, fee_usd=config.ORCHESTRATION_FEE_USD,
        payment_authorized=True))


if __name__ == "__main__":
    txn.run()
