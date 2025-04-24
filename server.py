#!/usr/bin/env python3
import os
import json
import requests
import logging
from mcp.server.fastmcp import FastMCP
from trello import TrelloClient
from dotenv import load_dotenv

load_dotenv()  # load TRELLO_KEY/TRELLO_TOKEN

# 1. Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("UniversalMCP")

# 2. Init MCP server
mcp = FastMCP("UniversalMCP")
logger.info("MCP server 'UniversalMCP' initialized")

# 3. Upstream APIs
properties_url = os.getenv("PROPERTY_URL","http://localhost:8000/get_properties")
visualise_url= os.getenv("CHART_URL","http://localhost:8000/get_charts")
update_property_api_base = os.getenv("UPDATE_PROPERTY_API_BASE", "https://staging-keplerchat-ysa2.encr.app/api/properties")
create_property_api_base = os.getenv("PROPERTY_API_BASE", "https://staging-keplerchat-ysa2.encr.app/api/properties")
HEADERS = {"Content-Type": "application/json"}

# 4. Tools

@mcp.tool(
    name="create_property",
    description=(
        "Create a new property via the Property Management API. "
        "Arguments: address1 (str), area (str), city (str), purchaseDate (str YYYY-MM-DD), "
        "developer (str), buyPrice (float), rentPrice (float), bedrooms (int), "
        "bathrooms (int), receptions (int), size (float)."
    )
)
def create_property(
    address1: str,
    area: str,
    city: str,
    purchaseDate: str,
    developer: str,
    buyPrice: float,
    rentPrice: float,
    bedrooms: int,
    bathrooms: int,
    receptions: int,
    size: float
) -> str:
    logger.info(
        "create_property called with %s, %s, %s, %s, %s, %s, %s, %d, %d, %d, %s",
        address1, area, city, purchaseDate, developer,
        buyPrice, rentPrice, bedrooms, bathrooms, receptions, size
    )
    url = create_property_api_base
    payload = {
        "address1": address1,
        "area": area,
        "city": city,
        "purchaseDate": purchaseDate,
        "developer": developer,
        "buyPrice": buyPrice,
        "rentPrice": rentPrice,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "receptions": receptions,
        "size": size
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error("Failed to create property: %s", e)
        return resp.text
    created = resp.json()
    logger.info("Property created successfully: %s", created)
    return json.dumps(created)



@mcp.tool(
    name="update_property_price",
    description=(
        "Update the rentPrice of a property by its ID. "
        "Arguments: id (int), rent_price (float), reason (str)."
    )
)
def update_property_price(id: int = 0, rent_price: float = 0.0, reason: str = "") -> str:
    logger.info(
        "update_property_price called with id=%s, rent_price=%s, reason=%s",
        id, rent_price, reason
    )

    url = f"{update_property_api_base}/{id}"
    payload = {
        "id": id,
        "rentPrice": rent_price,
        "reason": reason
    }

    resp = requests.put(url, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error("Failed to update property %s: %s", id, e)
        # return the raw body so the agent can see the error
        return resp.text

    updated = resp.json()
    logger.info("Property %s updated successfully: %s", id, updated)
    return json.dumps(updated)
@mcp.tool(
    name="get_properties",
    description="Fetch all json data from rent-history. Pass the full user query verbatim."
)
def get_properties(query: str = "") -> str:
    logger.info("get_properties called with query=%s", query)
    resp = requests.post(properties_url, headers=HEADERS, json={"question": query})
    resp.raise_for_status()
    data = resp.json()
    logger.info("get_properties returned %d items", len(data.get("result", data)))
    logger.info(data)
    return json.dumps(data)


@mcp.tool(
    name="get_chart",
    description="Given a natural-language query, fetch matching properties and generate a chart via the /visualise API."
)
def get_chart(query: str = "") -> str:
    logger.info("get_chart called with query=%s", query)

    # 1) Fetch the raw property records
    prop_resp = requests.post(visualise_url, headers=HEADERS, json={"question": query})
    prop_resp.raise_for_status()
    prop_data = prop_resp.json()
    records = prop_data.get("result", [])

    # 2) Call your /visualise endpoint with both question + data
    payload = {
        "question": query,
        "data": records
    }
    logger.debug("Posting to /visualise: %s", payload)
    viz_resp = requests.post(visualise_url, headers=HEADERS, json=payload)
    viz_resp.raise_for_status()

    # 3) Return the full visualization + answer JSON as a string
    result = viz_resp.json()
    logger.info("get_chart returned visualization payload")
    return json.dumps(result)


# 5. Trello tool
TRELLO_KEY   = "b6e8a8a9f4ba55ff0fe69665480bd9ac"
TRELLO_TOKEN = "ATTA7a977a86c8f45116eacf6993656820b80cfa1e3bffa08065a3fb2f0adb5c40d2FF1CD578"
LIST_ID      = "655211c8d08b8160082cd122"

# @mcp.tool(
#     name="create_trello_card",
#     description="Create a Trello card. Expects two arguments: name (str) and desc (str)."
# )
# def create_trello_card(name: str, desc: str = "") -> dict:
#     logger.info("create_trello_card called: name=%s", name)
#     client = TrelloClient(api_key=TRELLO_KEY, token=TRELLO_TOKEN)
#     trello_list = client.get_list(LIST_ID)
#     card = trello_list.add_card(name=name, desc=desc)
#     logger.info("Created Trello card id=%s", card.id)
#     return {"id": card.id, "url": card.url}

@mcp.tool(
    name="create_trello_card",
    description="Create a Trello card. make sure add proper name and description to the card. Returns the card URL as plain text."
)
def create_trello_card(name: str, desc: str = "") -> str:
    logger.info("create_trello_card called: name=%s", name)
    client = TrelloClient(api_key=TRELLO_KEY, token=TRELLO_TOKEN)
    trello_list = client.get_list(LIST_ID)
    card = trello_list.add_card(name=name, desc=desc)
    logger.info("Created Trello card id=%s url=%s", card.id, card.url)
    return f"Card created: {card.url}"

# 6. Run the loop
if __name__ == "__main__":
    logger.info("Starting MCP server run loop")
    mcp.run()
