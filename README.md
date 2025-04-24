# MCP Real Estate Agent

This repository contains:

- **`server.py`**: an MCP server exposing tools for:
  - `get_properties(query: str)` — fetches property records from the rent-history service
  - `get_chart(query: str)` — builds visualizations via the `/visualise` FastAPI
  - `create_trello_card(name: str, desc: str)` — creates Trello cards
  - `update_property_price(id: int, rent_price: float, reason: str)` — updates a property’s rent price
  - `create_property(...)` — creates a new property via the Property Management API

- **`client-api.py`**: a FastAPI application exposing a single endpoint:
  - `POST /run` accepts `{ "query": "<natural-language>" }`, plans and runs MCP tool calls, and returns aggregated results.

- **`Dockerfile`** and **`requirements.txt`** for containerized deployment.

---

## Setup

1. Create a `.env` file at project root:
   ```ini
   OPENAI_API_KEY=sk-...
   PROPERTY_API_BASE=https://staging-keplerchat-ysa2.encr.app
   TRELLO_KEY=your_trello_key
   TRELLO_TOKEN=your_trello_token
   ```

2. Install dependencies:
   ```bash
   pip install --no-cache-dir -r requirements.txt
   ```

## Running Locally

Start both MCP server and FastAPI app:

```bash
# In one terminal:
python server.py &

# In another:
uvicorn client-api:app --host 0.0.0.0 --port 8000 --log-level info
```

Open Swagger UI at http://localhost:8000/docs

---

## Docker

Build and run:

```bash
docker build -t mcp-agent .
docker run -p 8000:8000 mcp-agent
```

---

## API Usage

### POST `/run`

Send a natural-language query; the agent will plan and invoke tools.

**Request**

```bash
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "List all properties in Business Bay and update rent of ID 123 to 85000 because market adjustment"
  }'
```

**Response**

```json
{
  "properties": [ /* list of property records */ ],
  "updates": [ /* update confirmation */ ]
}
```

---

## Example Direct Tool Calls

Below are examples of calling the individual MCP tools via `curl` against the FastAPI:

1. **`get_properties`**

   ```bash
   curl -X POST "http://localhost:8000/run" \
     -H "Content-Type: application/json" \
     -d '{ "query": "get_properties: show 2 properties near Dubai Mall in Business Bay" }'
   ```

2. **`get_chart`**

   ```bash
   curl -X POST "http://localhost:8000/run" \
     -H "Content-Type: application/json" \
     -d '{ "query": "get_chart: visualize rent amounts for these properties" }'
   ```

3. **`update_property_price`**

   ```bash
   curl -X POST "http://localhost:8000/run" \
     -H "Content-Type: application/json" \
     -d '{ "query": "update_property_price: id 123 rent_price 85000 reason market adjustment" }'
   ```

4. **`create_property`**

   ```bash
   curl -X POST "http://localhost:8000/run" \
     -H "Content-Type: application/json" \
     -d '{ "query": "create_property: address1=123 Elm St, area=Business Bay, city=Dubai, purchaseDate=2025-04-24, developer=Acme, buyPrice=500000.0, rentPrice=25000.0, bedrooms=2, bathrooms=2, receptions=1, size=120.5" }'
   ```

---


