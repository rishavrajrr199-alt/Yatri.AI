"""Voyage:One — Itinerary Planner Agent.
Creates day-by-day plans via LLM (fallback: template), and re-plans on failure."""
import os
from datetime import datetime, timedelta
from uagents import Agent, Context

from common import config
from common.models import TripIntent, Itinerary, DayPlan, ReplanRequest

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

planner = Agent(name="voyage_one_planner", seed="voyage_one_planner_seed",
                port=8001, endpoint=["http://localhost:8001/submit"])


def llm_plan(intent: TripIntent) -> Itinerary:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        days = (datetime.strptime(intent.end_date, "%Y-%m-%d")
                - datetime.strptime(intent.start_date, "%Y-%m-%d")).days + 1
        resp = client.chat.completions.create(
            model="gpt-4o-mini", response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content":
                 "You are a travel planner. Return JSON {days:[{day:int,date,summary,"
                 "transport_pref:'train'|'flight'|'any',hotel_area_hint}]}."},
                {"role": "user", "content": f"Plan a {days}-day {intent.trip_style} trip to "
                 f"{intent.destination} from {intent.origin}, {intent.start_date} to "
                 f"{intent.end_date}. Budget ${intent.budget_total_usd}. Notes: {intent.notes}"},
            ])
        import json
        data = json.loads(resp.choices[0].message.content)
        return Itinerary(request_id=intent.request_id,
                         days=[DayPlan(**d) for d in data["days"]])
    except Exception:
        return None


def template_plan(intent: TripIntent) -> Itinerary:
    start = datetime.strptime(intent.start_date, "%Y-%m-%d")
    end = datetime.strptime(intent.end_date, "%Y-%m-%d")
    days = []
    i = 0
    d = start
    while d <= end:
        if i == 0:
            summary, tp = f"Travel {intent.origin} → {intent.destination}, check in, evening stroll", "train"
        elif d == end:
            summary, tp = f"Check out, return {intent.destination} → {intent.origin}", "flight"
        else:
            summary, tp = f"Full day exploring {intent.destination} highlights", "any"
        days.append(DayPlan(day=i + 1, date=d.strftime("%Y-%m-%d"), summary=summary,
                            transport_pref=tp, hotel_area_hint="city center"))
        i += 1
        d += timedelta(days=1)
    return Itinerary(request_id=intent.request_id, days=days,
                     est_lodging_budget_usd=intent.budget_total_usd * 0.5,
                     est_transport_budget_usd=intent.budget_total_usd * 0.3)


@planner.on_message(model=TripIntent)
async def plan(ctx: Context, sender: str, intent: TripIntent):
    itin = (llm_plan(intent) if config.OPENAI_API_KEY else None) or template_plan(intent)
    ctx.logger.info(f"Planned {len(itin.days)} days for {intent.request_id}")
    await ctx.send(sender, itin)


@planner.on_message(model=ReplanRequest)
async def replan(ctx: Context, sender: str, req: ReplanRequest):
    """Sold-out leg → swap train for flight (or vice versa) and re-emit."""
    ctx.logger.info(f"Replanning {req.request_id}: {req.reason}")
    # In full version we hold the last Itinerary per request_id; simple strategy:
    # swap the failed leg's preferred mode. Here we re-plan with a note.
    intent = TripIntent(request_id=req.request_id, destination="?", origin="?",
                        start_date="2026-01-01", end_date="2026-01-03",
                        notes=f"REPLAN because {req.reason}; failed leg {req.failed_leg}; "
                              f"use {'flight' if 'train' in (req.constraints or {}).get('mode','train') else 'train'} instead")
    # Restore real intent from session cache if present
    cached = LAST_INTENTS.get(req.request_id)
    if cached:
        cached.transport_pref_note = req.reason  # type: ignore
        intent = cached
    await ctx.send(sender, template_plan(intent))


LAST_INTENTS: dict = {}


@planner.on_message(model=TripIntent)
async def remember(ctx: Context, sender: str, intent: TripIntent):
    LAST_INTENTS[intent.request_id] = intent


if __name__ == "__main__":
    planner.run()
