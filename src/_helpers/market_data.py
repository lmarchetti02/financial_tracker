"""Fetches live market prices for portfolio holdings via the unofficial `yfinance` wrapper."""

from logging import getLogger

import yfinance as yf

logger = getLogger("financial_tracker")


def fetch_price(ticker: str) -> float | None:
    """Fetches the most recent price for a ticker.

    `yfinance` wraps unofficial, undocumented Yahoo Finance endpoints, so failures here are
    expected rather than exceptional: an unknown ticker, a Yahoo schema change, or a rate limit
    can all surface as different exception types. Any failure is treated the same way - the
    caller keeps showing the last known price instead of erroring.

    Args:
        ticker (str): The yfinance-compatible ticker symbol, e.g. "VWCE.DE".

    Returns:
        float | None: The latest price, or `None` if it couldn't be retrieved.
    """
    logger.info("Called 'fetch_price'")

    try:
        price = yf.Ticker(ticker).fast_info.last_price
    except Exception:
        logger.debug(f"Failed to fetch price for ticker '{ticker}'.", exc_info=True)
        return None

    if price is None:
        return None

    logger.debug(f"Fetched price for ticker '{ticker}': {price}")
    return float(price)
