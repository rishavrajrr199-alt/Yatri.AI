# Voyage:One — runnable multi-agent prototype

This is a **hackathon/demo prototype**, not a real booking engine. Transport inventory and payment/booking confirmations are mocked. Hotel search attempts Amadeus test API and falls back to demo hotels. Do not submit real passport data to this demo.

## Setup (Windows PowerShell)
1. Install Python 3.11 or a version supported by your installed `uagents` release.
2. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.template .env
   ```
3. Optional: add Amadeus test credentials and an OpenAI API key to `.env`.
4. Start each agent in a separate terminal from this project directory, in this order:
   ```powershell
   python itinerary_planner.py
   python transport_agent.py
   python accommodation_agent.py
   python transaction_agent.py
   ```
   Copy each printed agent address into `.env` as `PLANNER_ADDR`, `TRANSPORT_ADDR`, `HOTEL_ADDR`, and `TXN_ADDR`, then restart those agents.
5. Start `python concierge.py` last. Register the concierge with Agentverse and connect it to ASI:One using the currently supported chat protocol/card schema.

## Important integration notes
- The `common/` package was missing from the supplied files; this bundle adds `config.py`, `models.py`, and `cards.py`.
- Transport agent is rewritten to use the same typed models as Concierge; its inventory is deterministic mock data.
- Card payloads are illustrative. Confirm the exact ASI:One interactive-card schema and chat response envelope in current Fetch.ai documentation before expecting buttons/forms to work in the live interface.
- Payment is a **mock authorization only**. It does not charge money or create actual flight/train/hotel bookings. Confirmation codes are demo IDs.
- The supplied concierge/planner logic is a starter and should be tested against the exact `uagents` version installed. Do not claim real-time availability or real bookings in a presentation.
