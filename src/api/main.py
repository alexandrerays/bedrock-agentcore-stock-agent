"""FastAPI application for stock agent."""

import os
import json
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent.graph import create_streaming_agent
from src.knowledge.retriever import KnowledgeBaseRetriever
from src.api.auth import get_current_user, verify_token_for_development

# Global agent and retriever
agent = None
knowledge_retriever = None


class InvokeRequest(BaseModel):
    """Request model for invoke endpoint."""
    input: dict
    user_id: Optional[str] = None


class StreamResponse(BaseModel):
    """Response model for streaming events."""
    type: str
    content: str
    step: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown.
    Initializes the agent and knowledge base on startup.
    """
    global agent, knowledge_retriever

    print("Starting up stock agent...")

    try:
        # Initialize knowledge retriever
        print("Initializing knowledge base...")
        knowledge_retriever = KnowledgeBaseRetriever(
            use_bedrock=os.getenv("USE_BEDROCK_EMBEDDINGS", "false").lower() == "true"
        )
        knowledge_retriever.build_vector_store(force_rebuild=False)
        print("Knowledge base initialized")

        # Create agent
        print("Creating agent...")
        agent = create_streaming_agent(knowledge_retriever)
        print("Agent created and ready")

    except Exception as e:
        print(f"Error during startup: {e}")
        import traceback
        traceback.print_exc()

        # Fail fast in local/dev so you see the real error immediately
        if os.getenv("FAIL_FAST", "true").lower() == "true":
            raise

    yield

    print("Shutting down stock agent...")


# Create FastAPI app
app = FastAPI(
    title="Stock Agent API",
    description="AI agent for querying stock prices and Amazon financial data",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent_ready": agent is not None,
        "knowledge_base_ready": knowledge_retriever is not None
    }


async def event_stream(
    query: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream agent events for a query.

    Args:
        query: User query
        user_id: User identifier

    Yields:
        JSON-formatted event strings
    """
    if agent is None:
        yield json.dumps({
            "type": "error",
            "content": "Agent not initialized"
        }) + "\n"
        return

    print(f"Processing query for user {user_id}: {query}")

    try:
        # Import here to avoid issues with event loop
        from langchain_core.messages import HumanMessage

        initial_state = {
            "messages": [HumanMessage(content=query)],
            "question": query,
            "step_count": 0,
            "knowledge_retriever": knowledge_retriever
        }

        # Stream agent events
        step = 0
        async for event in agent.astream(initial_state):
            step += 1

            # Extract message from agent node
            if "agent" in event:
                messages = event["agent"].get("messages", [])
                if messages:
                    last_msg = messages[-1]

                    # Send thinking/reasoning
                    if hasattr(last_msg, "content") and last_msg.content:
                        yield json.dumps({
                            "type": "agent_reasoning",
                            "content": str(last_msg.content)[:1000],
                            "step": step
                        }) + "\n"

                    # Send tool calls if any
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            tool_name = tool_call.get("name", tool_call.get("type", "unknown"))
                            tool_input = tool_call.get("args", {})
                            yield json.dumps({
                                "type": "tool_call",
                                "tool": tool_name,
                                "input": tool_input,
                                "step": step
                            }) + "\n"

            # Extract results from tool node
            if "tools" in event:
                messages = event["tools"].get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content"):
                        content = str(msg.content)
                        # Truncate very long results
                        if len(content) > 2000:
                            content = content[:2000] + "... [truncated]"
                        yield json.dumps({
                            "type": "tool_result",
                            "content": content,
                            "step": step
                        }) + "\n"

        # Send final response
        final_msg = event.get("agent", event).get("messages", [])
        if final_msg:
            last = final_msg[-1]
            if hasattr(last, "content"):
                yield json.dumps({
                    "type": "final_response",
                    "content": str(last.content),
                    "step": step
                }) + "\n"

    except Exception as e:
        print(f"Error in event stream: {e}")
        import traceback
        traceback.print_exc()
        yield json.dumps({
            "type": "error",
            "content": f"Error processing query: {str(e)}"
        }) + "\n"


@app.post("/invocations")
async def invocations(request: InvokeRequest):
    """
    AWS Bedrock Agentcore endpoint for agent invocation.
    This is the standard endpoint used by Bedrock Agentcore.

    Args:
        request: Invoke request with query

    Returns:
        StreamingResponse with newline-delimited JSON events
    """
    # Extract query from request
    query = request.input.get("prompt") or request.input.get("query")

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No prompt or query provided in request input"
        )

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not initialized"
        )

    # Create streaming response for Agentcore
    return StreamingResponse(
        event_stream(query, "agentcore-user"),
        media_type="application/x-ndjson"  # Newline-delimited JSON
    )


@app.post("/invoke")
async def invoke(
    request: InvokeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Invoke the agent with a query and stream responses.
    This endpoint requires authentication via Cognito.

    Args:
        request: Invoke request with query
        current_user: Current authenticated user

    Returns:
        StreamingResponse with newline-delimited JSON events
    """
    # Extract query from request
    query = request.input.get("prompt") or request.input.get("query")

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No prompt or query provided in request input"
        )

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not initialized"
        )

    # Get user identifier
    user_id = current_user.get("sub", current_user.get("cognito:username", "unknown"))

    # Create streaming response
    return StreamingResponse(
        event_stream(query, user_id),
        media_type="application/x-ndjson"  # Newline-delimited JSON
    )


@app.post("/invoke-dev")
async def invoke_dev(request: InvokeRequest):
    """
    Development endpoint without authentication.
    Only works if SKIP_AUTH=true or ENVIRONMENT=development.
    """
    env = os.getenv("ENVIRONMENT", "production")
    skip_auth = os.getenv("SKIP_AUTH", "false").lower() == "true"

    if env == "production" and not skip_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development endpoint disabled in production"
        )

    # Extract query
    query = request.input.get("prompt") or request.input.get("query")

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No prompt or query provided"
        )

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not initialized"
        )

    return StreamingResponse(
        event_stream(query, "dev-user"),
        media_type="application/x-ndjson"
    )


@app.get("/knowledge-base")
async def get_knowledge_base_stats(current_user: dict = Depends(get_current_user)):
    """Get statistics about the knowledge base."""
    if not knowledge_retriever:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base not initialized"
        )

    return knowledge_retriever.get_stats()


if __name__ == "__main__":
    import uvicorn

    # AWS Bedrock Agentcore expects the app to listen on port 8080
    port = int(os.getenv("PORT", "8080"))

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
