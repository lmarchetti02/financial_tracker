"""Unit tests for `_helpers.market_data`."""

from unittest.mock import MagicMock, patch

from _helpers.market_data import fetch_price


class TestFetchPrice:
    """Tests for `fetch_price`."""

    @patch("_helpers.market_data.yf.Ticker")
    def test_returns_the_latest_price_on_success(self, mock_ticker: MagicMock) -> None:
        """A successful lookup returns `fast_info.last_price` as a float."""
        mock_ticker.return_value.fast_info.last_price = 163.74

        assert fetch_price("VWCE.DE") == 163.74

    @patch("_helpers.market_data.yf.Ticker")
    def test_returns_none_when_the_price_is_missing(self, mock_ticker: MagicMock) -> None:
        """A `None` price (e.g. an unlisted instrument) is passed through as `None`."""
        mock_ticker.return_value.fast_info.last_price = None

        assert fetch_price("VWCE.DE") is None

    @patch("_helpers.market_data.yf.Ticker")
    def test_returns_none_when_the_lookup_raises(self, mock_ticker: MagicMock) -> None:
        """Any exception from the unofficial API (bad ticker, network issue, schema change) yields `None`."""
        mock_ticker.side_effect = KeyError("exchangeTimezoneName")

        assert fetch_price("NOT_A_REAL_TICKER") is None
