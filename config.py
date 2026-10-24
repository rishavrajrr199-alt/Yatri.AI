import os
from dotenv import load_dotenv
load_dotenv()

AMADEUS_HOST = os.getenv("AMADEUS_HOST", "https://test.api.amadeus.com")
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CONCIERGE_SEED = os.getenv("CONCIERGE_SEED", "voyage_one_concierge_seed")
PLANNER_SEED = os.getenv("PLANNER_SEED", "voyage_one_planner_seed")
TRANSPORT_SEED = os.getenv("TRANSPORT_SEED", "voyage_one_transport_seed")
HOTEL_SEED = os.getenv("HOTEL_SEED", "voyage_one_hotel_seed")
TXN_SEED = os.getenv("TXN_SEED", "voyage_one_txn_seed")
PLANNER_ADDR = os.getenv("PLANNER_ADDR", "")
TRANSPORT_ADDR = os.getenv("TRANSPORT_ADDR", "")
HOTEL_ADDR = os.getenv("HOTEL_ADDR", "")
TXN_ADDR = os.getenv("TXN_ADDR", "")
ORCHESTRATION_FEE_USD = float(os.getenv("ORCHESTRATION_FEE_USD", "5"))
