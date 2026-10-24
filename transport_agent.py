"""Voyage:One transport agent. Deterministic mock inventory; no real tickets are sold."""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import random
from uagents import Agent, Context
from common import config
from common.models import TransportQuery, TransportOption, TransportResult

transport = Agent(name="voyage_one_transport", seed=config.TRANSPORT_SEED,
                  port=8002, endpoint=["http://localhost:8002/submit"])

@transport.on_message(model=TransportQuery)
async def on_query(ctx: Context, sender: str, q: TransportQuery):
    # Demo data only. It deliberately returns both requested modes where relevant.
    modes = [q.mode] if q.mode in ("train", "flight") else ["train", "flight"]
    options=[]
    for i, mode in enumerate(modes):
        rng=random.Random(f"{q.request_id}:{q.origin_iata}:{q.destination_iata}:{q.date}:{mode}")
        options.append(TransportOption(
            option_id=f"{mode.upper()}-{q.request_id}-{i+1}", mode=mode,
            origin=q.origin_iata, destination=q.destination_iata, date=q.date,
            departure=f"{rng.randint(7,18):02d}:30", arrival=f"{rng.randint(10,22):02d}:15",
            price_usd=round(rng.uniform(35,180) if mode=="train" else rng.uniform(90,320),2),
            sold_out=False, provider="Mock demo inventory"))
    await ctx.send(sender, TransportResult(request_id=q.request_id, options=options, error=""))

if __name__ == "__main__":
    transport.run()
