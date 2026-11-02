# -*- coding: utf-8 -*-
"""Regression tests for YfinanceFetcher daily data normalization."""

import pandas as pd
from unittest.mock import patch

from data_provider.yfinance_fetcher import YfinanceFetcher


def test_daily_download_preserves_unadjusted_ohlc() -> None:
    raw = pd.DataFrame(
        {"Open": [423.0], "High": [454.0], "Low": [422.5],
         "Close": [433.0], "Adj Close": [431.33], "Volume": [14711000]},
        index=pd.DatetimeIndex(["2026-01-06"]),
    )
    fetcher = YfinanceFetcher()
    with patch("yfinance.download", return_value=raw) as download:
        result = fetcher._fetch_raw_data("6488.TWO", "2026-01-06", "2026-01-07")
    assert download.call_args.kwargs["auto_adjust"] is False
    normalized = fetcher._normalize_data(result, "6488.TWO")
    assert normalized.iloc[0]["high"] == 454.0
    assert normalized.iloc[0]["close"] == 433.0


def test_normalize_daily_data_recovers_unnamed_datetime_index_date_column() -> None:
    fetcher = YfinanceFetcher()
    raw = pd.DataFrame(
        {
            "Open": [10.0, 10.5],
            "High": [11.0, 11.2],
            "Low": [9.8, 10.1],
            "Close": [10.8, 11.0],
            "Volume": [1000, 1200],
        },
        index=pd.DatetimeIndex(["2026-05-25", "2026-05-26"]),
    )

    normalized = fetcher._normalize_data(raw, "DRAM")
    cleaned = fetcher._clean_data(normalized)

    assert "date" in normalized.columns
    assert cleaned["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-05-25", "2026-05-26"]
