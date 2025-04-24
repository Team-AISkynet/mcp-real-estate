#!/usr/bin/env python3
import os
import json
import logging
import asyncio
from typing import Any, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# ————————————————————————————————————————————————————————————————
# Configuration & Logging
# ————————————————————————————————————————————————————————————————
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Please set OPENAI_API_KEY in your .env file.")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("MCPClient")

# MCP Server parameters\ n# Define how to launch your MCP server process
SERVER_CMD = StdioServerParameters(
    command="python",
    args=["server.py"],
)

# Initialize the LLM for planning
PLANNER = ChatOpenAI(
    model="gpt-4.1-mini",
    openai_api_key=OPENAI_API_KEY,
    temperature=0
)

# Planner prompt prefix
PREFIX = """
You have five tools:
  • get_properties(query: str) → returns JSON object with all the information
  • get_chart(query: str)      → returns JSON object with chart data
  • create_trello_card(name: str, desc: str) → returns plain text "Card created: <url>"
  • update_property_price(id: int, rent_price: float, reason: str) → updates a property's rent price
  • create_property(address1: str, area: str, city: str, purchaseDate: str, developer: str, buyPrice: float, rentPrice: float, bedrooms: int, bathrooms: int, receptions: int, size: float) → creates a new property

Analyze the user's query and return a JSON plan of tasks:
{"tasks": [
    {"action": "get_properties", "params": {"query": "..."}},
    {"action": "create_trello_card",  "params": {"mode": "per_item"}},
    {"action": "update_property_price", "params": {"id": 123, "rent_price": 10000.0, "reason": "..."}},
    {"action": "create_property",    "params": {"address1": "...", "area": "...", "city": "...", "purchaseDate": "YYYY-MM-DD", "developer": "...", "buyPrice": 100000.0, "rentPrice": 5000.0, "bedrooms": 2, "bathrooms": 1, "receptions": 1, "size": 120.5}}
]}
Respond ONLY with this JSON.
"""

# Create FastAPI app with Swagger/OpenAPI
app = FastAPI(
    title="MCP Agent API",
    description="Exposes a single `/run` endpoint that accepts a natural-language query, plans and runs MCP tool invocations, and returns aggregated results.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class QueryRequest(BaseModel):
    query: str

@app.post(
    "/run",
    summary="Run MCP agent tasks",
    response_description="Aggregated results from MCP tools"
)
async def run_agent(request: QueryRequest) -> Dict[str, Any]:
    user_query = request.query
    logger.info("Received query: %s", user_query)

    # 1) Generate planning prompt
    messages = [SystemMessage(content=PREFIX), HumanMessage(content=user_query)]
    try:
        plan_resp = await PLANNER.agenerate([messages])
        plan_text = plan_resp.generations[0][0].text.strip()
        plan = json.loads(plan_text)
    except Exception as e:
        logger.error("Planning failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Planning error: {e}")

    # 2) Execute tasks via MCP
    state: Dict[str, Any] = {"properties": None, "chart": None, "cards": [], "updates": [], "created": []}
    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await load_mcp_tools(session)

            for task in plan.get("tasks", []):
                action = task.get("action")
                params = task.get("params", {}) or {}
                logger.info("Executing task %s with params %s", action, params)

                if action in ("get_properties", "get_chart") and isinstance(params, str):
                    params = {"query": params}

                try:
                    result = await session.call_tool(action, arguments=params)
                except Exception as e:
                    logger.exception("Tool call %s failed: %s", action, e)
                    continue

                # Extract raw text content
                content = getattr(result, 'content', result)
                items = content if isinstance(content, (list, tuple)) else [content]
                raw = "".join(getattr(i, 'text', getattr(i, 'content', str(i))) for i in items)
                logger.debug("Result %s: %s", action, raw)

                try:
                    obj = json.loads(raw)
                except:
                    obj = raw

                # Store results by action
                if action == "get_properties":        state["properties"] = obj
                elif action == "get_chart":           state["chart"] = obj
                elif action == "create_trello_card" and not params.get("mode"): state["cards"].append(obj)
                elif action == "update_property_price": state["updates"].append(obj)
                elif action == "create_property":      state["created"].append(obj)

    # Build response only with non-empty entries
    response = {k: v for k, v in state.items() if v}
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 9000)))