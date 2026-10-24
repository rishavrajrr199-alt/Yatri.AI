"""ASI:One card payload helpers. Validate the exact card schema against the current ASI:One docs."""
def hotel_carousel(options):
    return {"type":"carousel","title":"Choose your stay","items":[
        {"title":h.name,"description":f"{h.area} · ★ {h.rating} · ${h.price_per_night_usd:.0f}/night",
         "image_url":h.image_url,"actions":[{"label":"Select","action":"select_hotel","hotel_id":h.hotel_id}]}
        for h in options]}

def traveler_form():
    return {"type":"form","title":"Traveler details","fields":[
        {"name":"traveler_name","label":"Full name","type":"text","required":True},
        {"name":"traveler_dob","label":"Date of birth","type":"date","required":True},
        {"name":"passport_number","label":"Passport number (optional)","type":"text","required":False}],
        "submit_action":"submit_traveler"}

def payment_card(total, fee, summary):
    return {"type":"detail","title":"Authorize trip payment",
        "content":{"summary":summary,"trip_total_usd":round(total,2),
                   "orchestration_fee_usd":round(fee,2),"amount_due_usd":round(total+fee,2)},
        "actions":[{"label":"Authorize (demo only)","action":"authorize_payment","authorized":True}]}

def itinerary_detail_card(conf, plan_text):
    return {"type":"detail","title":"Voyage:One · Trip summary",
        "content":{"itinerary":plan_text,"hotel_confirmation":conf.hotel_confirmation,
                   "transport_confirmations":conf.transport_confirmations,
                   "trip_total_usd":conf.total_usd,"orchestration_fee_usd":conf.fee_usd,
                   "payment_authorized":conf.payment_authorized}}

def render(card):
    return card

def parse_user_card_response(text):
    import json
    try:
        data=json.loads(text)
        if isinstance(data,dict) and "asi1_card_response" in data:
            return data["asi1_card_response"]
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}
