"""Stock market tools for the LangGraph agent."""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Any, Optional


def retrieve_realtime_stock_price(ticker: str) -> dict[str, Any]:
    """
    Retrieve the current real-time stock price for a given ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'AMZN')

    Returns:
        Dictionary containing price information
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")

        if data.empty:
            return {
                "error": f"No data found for ticker {ticker}",
                "ticker": ticker
            }

        current_price = data['Close'].iloc[-1]
        info = stock.info

        return {
            "ticker": ticker,
            "current_price": float(current_price),
            "currency": info.get("currency", "USD"),
            "previous_close": float(info.get("previousClose", 0)),
            "change": float(current_price) - float(info.get("previousClose", 0)),
            "change_percent": ((float(current_price) - float(info.get("previousClose", 0))) / float(info.get("previousClose", 1))) * 100,
            "timestamp": datetime.now().isoformat(),
            "market_cap": info.get("marketCap"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        return {
            "error": str(e),
            "ticker": ticker
        }


def retrieve_historical_stock_price(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "3mo"
) -> dict[str, Any]:
    """
    Retrieve historical stock price data for a given ticker.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        period: Period if dates not specified (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dictionary containing historical price data
    """
    try:
        stock = yf.Ticker(ticker)

        if start_date and end_date:
            data = stock.history(start=start_date, end=end_date)
        else:
            data = stock.history(period=period)

        if data.empty:
            return {
                "error": f"No data found for ticker {ticker}",
                "ticker": ticker
            }

        # Calculate statistics
        prices = data['Close'].tolist()
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)

        # Format data for response
        historical_data = [
            {
                "date": str(date.date()),
                "open": float(data.loc[date, 'Open']),
                "high": float(data.loc[date, 'High']),
                "low": float(data.loc[date, 'Low']),
                "close": float(data.loc[date, 'Close']),
                "volume": int(data.loc[date, 'Volume']) if 'Volume' in data else None,
            }
            for date in data.index[-20:]  # Return last 20 trading days
        ]

        return {
            "ticker": ticker,
            "period": period if not (start_date and end_date) else f"{start_date} to {end_date}",
            "data_points": len(prices),
            "min_price": float(min_price),
            "max_price": float(max_price),
            "average_price": float(avg_price),
            "latest_price": float(prices[-1]),
            "price_change": float(prices[-1]) - float(prices[0]),
            "price_change_percent": ((float(prices[-1]) - float(prices[0])) / float(prices[0])) * 100,
            "historical_data": historical_data,
        }
    except Exception as e:
        return {
            "error": str(e),
            "ticker": ticker
        }


# Define tools for LangGraph
TOOLS = [
    {
        "name": "retrieve_realtime_stock_price",
        "description": "Get the current real-time stock price for a ticker. Returns current price, previous close, change, and market data.",
        "func": retrieve_realtime_stock_price,
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AMZN' for Amazon)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "retrieve_historical_stock_price",
        "description": "Get historical stock price data for a ticker. Can specify a date range or use a predefined period. Returns price statistics and recent trading data.",
        "func": retrieve_historical_stock_price,
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (optional)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (optional)"
                },
                "period": {
                    "type": "string",
                    "description": "Period if dates not specified: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max",
                    "default": "3mo"
                }
            },
            "required": ["ticker"]
        }
    }
]
