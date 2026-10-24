# Voyage:One — Autonomous Travel Orchestrator

Multi-agent travel planning entirely inside ASI:One chat. Five uAgents:

| Agent | Role | Port |
|---|---|---|
| concierge | User-facing router (ASI:One connected), cards, session state | 8000 |
| itinerary_planner | LLM day-by-day planning + autonomous replan on failure | 8001 |
| transport_agent | Amadeus Flight Offers + rail (fallback) | 8002 |
| accommodation_agent | Amadeus hotel search + curated fallback | 8003 |
| transaction_agent | Payment authorization, $5 fee, confirmations | 8004 |

## Quickstart

1. `pip install -r requirements.txt`
2. Copy `.env` template, fill Amadeus test credentials (free at developers.amadeus.com).
3. Run each agent in its own terminal: `python transport_agent.py`, etc.
   First run prints each agent's **address** — paste them into `common/config.py`
   (PLANNER_ADDR, TRANSPORT_ADDR, HOTEL_ADDR, TXN_ADDR) and restart.
4. Register the concierge on Agentverse and connect it to ASI:One
   (Agentverse → My Agents → Connect to ASI:One / Chat protocol).
5. In ASI:One, message the concierge:
   > "I want a 3-day trip to Kyoto from Tokyo. Bullet train there, fly back,
   > stay in a traditional Ryokan. Budget $800."

## Hackathon criteria coverage
- **Multi-agent collaboration**: 5 agents exchanging typed models via uAgents.
- **ASI:One Interactive Cards**: hotel carousel, traveler-details form, final
  itinerary/boarding-pass detail card, payment authorization card.
- **Payment Protocol**: Transaction Agent presents a payment request card with
  a $5 orchestration fee; mock authorization wired for demo (swap in Fetch.ai
  Payment Protocol or Stripe test for real money).
- **Error handling / autonomy**: sold-out transport legs trigger a ReplanRequest
  to the planner, which swaps train↔flight and re-plans without user intervention.
- **Monetization**: flat orchestration fee + note on affiliate commissions.

## Demo script
1. User states vague intent → Concierge parses (LLM) and broadcasts.
2. Planner returns day-by-day plan; transport + hotel agents search in parallel.
3. Carousel of hotels → user taps "Select".
4. Form for name/DOB/passport → user submits.
5. Payment card → user authorizes.
6. Final detail card with confirmation numbers for train, flight, hotel.

## Notes
- Amadeus **test** environment: free, sandbox data; some routes return 404 —
  the transport/hotel agents include deterministic mock fallbacks so the demo
  always completes.
- For production: replace mocks with Duffel/Amadeus booking APIs, real rail
  providers, and the Fetch.ai Payment Protocol (or Stripe).
