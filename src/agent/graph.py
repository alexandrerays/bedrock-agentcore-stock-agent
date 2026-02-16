"""LangGraph ReAct agent for stock queries."""

import os
import json
from typing import Any, TypedDict, Optional
from typing_extensions import NotRequired

from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_aws import ChatBedrockConverse

from src.agent.tools import (
    retrieve_realtime_stock_price,
    retrieve_historical_stock_price,
)
from src.knowledge.retriever import KnowledgeBaseRetriever


class AgentState(TypedDict):
    """State schema for the agent graph."""
    messages: list[BaseMessage]
    question: str
    step_count: int
    knowledge_retriever: NotRequired[KnowledgeBaseRetriever]


def create_agent(knowledge_retriever: Optional[KnowledgeBaseRetriever] = None):
    """
    Create a LangGraph ReAct agent for stock queries.

    Args:
        knowledge_retriever: KnowledgeBaseRetriever instance for document search

    Returns:
        Compiled LangGraph agent
    """
    # Initialize Bedrock client
    region = os.getenv("AWS_REGION", "us-east-1")

    try:
        llm = ChatBedrockConverse(
            model=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
            provider="anthropic",
            region_name=region,
            temperature=0.3,
            max_tokens=2048
        )
        print(f"Using Claude 3.5 Haiku model in {region}")
    except Exception as e:
        raise RuntimeError(
            f"Bedrock init failed and fallback is disabled. Error: {e}"
        )


    # Define tools for the agent
    @tool
    def search_amazon_documents(query: str) -> str:
        """
        Search Amazon financial documents for relevant information.

        Args:
            query: Query to search

        Returns:
            Relevant document excerpts
        """
        if knowledge_retriever is None:
            return "Knowledge retriever not available"

        try:
            docs = knowledge_retriever.retrieve_documents(query, k=3)
            if not docs:
                return f"No relevant documents found for query: {query}"

            results = []
            for doc in docs:
                source = doc.metadata.get("source_file", "unknown")
                content = doc.page_content[:500]  # Limit content
                results.append(f"[{source}]\n{content}")

            return "\n\n".join(results)
        except Exception as e:
            return f"Error searching documents: {str(e)}"

    @tool
    def get_realtime_stock_price(ticker: str) -> str:
        """Get the current stock price for a ticker."""
        result = retrieve_realtime_stock_price(ticker)
        return json.dumps(result, indent=2)

    @tool
    def get_historical_stock_price(
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "3mo"
    ) -> str:
        """Get historical stock price data."""
        result = retrieve_historical_stock_price(ticker, start_date, end_date, period)
        return json.dumps(result, indent=2)

    # Create tool list for agent
    tools = [
        get_realtime_stock_price,
        get_historical_stock_price,
        search_amazon_documents
    ]

    # Create tool map for routing
    tool_map = {
        "get_realtime_stock_price": get_realtime_stock_price,
        "get_historical_stock_price": get_historical_stock_price,
        "search_amazon_documents": search_amazon_documents,
    }

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Define agent node
    def agent_node(state: AgentState) -> dict:
        """Run agent logic."""
        messages = state["messages"]

        # Invoke LLM with tools
        response = llm_with_tools.invoke(messages)

        return {
            "messages": messages + [response],
            "step_count": state.get("step_count", 0) + 1
        }

    # Define tool execution node
    def tool_node(state: AgentState) -> dict:
        """Execute tool calls."""
        messages = state["messages"]
        last_message = messages[-1]

        tool_calls = getattr(last_message, "tool_calls", []) or []
        if not tool_calls:
            return {"messages": messages}

        tool_results: list[ToolMessage] = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name") or tool_call.get("type")
            tool_input = tool_call.get("args") or {}

            # Claude/Converse uses `id` for tool calls (e.g., "tooluse_...")
            tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id")
            if not tool_call_id:
                # Hard fail with a clear message (prevents silent graph breakage)
                tool_results.append(
                    ToolMessage(
                        content=f"Missing tool_call_id for tool {tool_name}. Raw tool_call: {tool_call}",
                        tool_call_id="missing_tool_call_id",
                    )
                )
                continue

            print(f"Calling tool: {tool_name} with input: {tool_input} (id={tool_call_id})")

            tool_func = tool_map.get(tool_name)
            if not tool_func:
                result_text = f"Tool '{tool_name}' not found. Available: {list(tool_map.keys())}"
            else:
                try:
                    # StructuredTool.invoke expects a dict of arguments
                    result = tool_func.invoke(tool_input)
                    result_text = str(result)
                except Exception as e:
                    result_text = f"Error executing tool '{tool_name}': {str(e)}"

            # ✅ IMPORTANT: LangGraph expects `tool_call_id`, not `tool_use_id`
            tool_results.append(
                ToolMessage(
                    content=result_text,
                    tool_call_id=tool_call_id,
                )
            )

        return {"messages": messages + tool_results}


    # Define router to decide next step
    def route_agent(state: AgentState) -> str:
        """Route to next node based on agent output."""
        messages = state["messages"]
        last_message = messages[-1]

        # Check if we should stop (reached max steps or no tool calls)
        if state.get("step_count", 0) >= 10:
            return END

        # Check for tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        return END

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Add edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        route_agent,
        {
            "tools": "tools",
            END: END
        }
    )
    workflow.add_edge("tools", "agent")

    # Compile
    return workflow.compile()


def create_streaming_agent(knowledge_retriever: Optional[KnowledgeBaseRetriever] = None):
    """
    Create an agent configured for streaming responses.

    Args:
        knowledge_retriever: KnowledgeBaseRetriever instance

    Returns:
        Compiled streaming-ready agent
    """
    return create_agent(knowledge_retriever)


async def run_agent_stream(
    query: str,
    agent: Any,
    knowledge_retriever: Optional[KnowledgeBaseRetriever] = None
):
    """
    Run agent and stream events.

    Args:
        query: User query
        agent: Compiled agent graph
        knowledge_retriever: Optional knowledge retriever

    Yields:
        Event dictionaries for streaming
    """
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "question": query,
        "step_count": 0,
        "knowledge_retriever": knowledge_retriever
    }

    # Use astream for async streaming
    async for event in agent.astream(initial_state):
        # Format event for client
        if "agent" in event:
            agent_message = event["agent"]["messages"][-1]
            if hasattr(agent_message, "content") and agent_message.content:
                yield {
                    "type": "agent_message",
                    "content": agent_message.content
                }

        if "tools" in event:
            tool_messages = event["tools"]["messages"]
            for msg in tool_messages:
                if hasattr(msg, "name") or hasattr(msg, "content"):
                    yield {
                        "type": "tool_result",
                        "content": getattr(msg, "content", str(msg))
                    }

    # Final response
    final_messages = event.get("agent", event).get("messages", [])
    if final_messages:
        last_message = final_messages[-1]
        if hasattr(last_message, "content"):
            yield {
                "type": "final_response",
                "content": last_message.content
            }
