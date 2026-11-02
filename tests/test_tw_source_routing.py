"""Taiwan requests must never fall back to China-only providers."""
from unittest.mock import Mock, patch
from types import SimpleNamespace
from pathlib import Path

import pandas as pd
import pytest

from data_provider.base import DataFetchError, DataFetcherManager, _market_tag
from data_provider.yfinance_fetcher import YfinanceFetcher
from tests.test_tw_market_support import _FakeFetcher


CODES = ["2330.TW", "2303.TW", "6488.TWO", "00878.TW"]


@pytest.fixture(autouse=True)
def reset_source_health():
    DataFetcherManager.reset_daily_source_health()
    yield
    DataFetcherManager.reset_daily_source_health()


def manager_with_sources(fail=False):
    china = []
    for name in ("BaostockFetcher", "PytdxFetcher", "AkshareFetcher", "EfinanceFetcher", "TickFlowFetcher"):
        source = _FakeFetcher(name, should_fail=True)
        for method in ("get_stock_name", "get_realtime_quote", "get_stock_list",
                       "get_chip_distribution", "prefetch_daily_klines", "prefetch_realtime_quotes"):
            setattr(source, method, Mock(side_effect=AssertionError("China-only source called")))
        china.append(source)
    yahoo = _FakeFetcher("YfinanceFetcher", should_fail=fail)
    yahoo.get_stock_name = Mock(return_value=None if fail else "Taiwan issuer")
    yahoo.get_realtime_quote = Mock(return_value=None)
    return DataFetcherManager(fetchers=china + [yahoo]), china, yahoo


@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize("fail", [False, True])
def test_tw_names_daily_quotes_and_failure_isolation(code, fail):
    manager, china, yahoo = manager_with_sources(fail)
    assert _market_tag(code) == "tw"
    with patch("data_provider.base.STOCK_NAME_MAP", {}), patch("data_provider.base.get_index_stock_name", return_value=None):
        assert manager.get_stock_name(code, allow_realtime=False) == ("" if fail else "Taiwan issuer")
    yahoo.get_stock_name.assert_called_once_with(code)
    with patch("data_provider.base.record_provider_run_started"), patch("data_provider.base.record_provider_run"):
        if fail:
            with pytest.raises(DataFetchError):
                manager.get_daily_data(code)
        else:
            frame, source = manager.get_daily_data(code)
            assert not frame.empty and source == "YfinanceFetcher"
    assert manager.get_realtime_quote(code) is None
    assert manager.get_chip_distribution(code) is None
    assert manager.get_belong_boards(code) == []
    assert manager.get_capital_flow_context(code)["status"] == "not_supported"
    assert manager.prefetch_daily_klines([code]) == 0
    assert manager.prefetch_realtime_quotes([code] * 5) == 0
    for source in china:
        assert source.calls == []
        for method in ("get_stock_name", "get_realtime_quote", "get_stock_list", "get_chip_distribution",
                       "prefetch_daily_klines", "prefetch_realtime_quotes"):
            getattr(source, method).assert_not_called()


def test_tw_bulk_names_skip_china_lists():
    manager, china, yahoo = manager_with_sources()
    with patch("data_provider.base.STOCK_NAME_MAP", {}), patch("data_provider.base.get_index_stock_name", return_value=None):
        assert manager.batch_get_stock_names(CODES) == dict.fromkeys(CODES, "Taiwan issuer")
    for source in china:
        source.get_stock_list.assert_not_called()
        source.get_stock_name.assert_not_called()


@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize("info, expected", [
    ({"shortName": "Taiwan issuer", "longName": "Long issuer"}, "Taiwan issuer"),
    ({"longName": "Long issuer"}, "Long issuer"),
    ({}, None),
])
def test_yahoo_name_without_price_request(code, info, expected):
    with patch("yfinance.Ticker") as ticker:
        ticker.return_value.info = info
        assert YfinanceFetcher().get_stock_name(code) == expected
        ticker.assert_called_once_with(code)
        ticker.return_value.history.assert_not_called()


def test_yahoo_name_failure_and_code_placeholder():
    with patch("yfinance.Ticker") as ticker:
        ticker.side_effect = RuntimeError("Yahoo unavailable")
        assert YfinanceFetcher().get_stock_name("2330.TW") is None
    assert YfinanceFetcher._stock_name_from_info(
        {"shortName": "2330.TW", "longName": "Taiwan Semiconductor"}, "2330.TW"
    ) == "Taiwan Semiconductor"


def test_technical_indicators_are_calculated_locally():
    frame = pd.DataFrame({"close": range(1, 61), "volume": [100] * 60})
    result = YfinanceFetcher()._calculate_indicators(frame)
    assert result.iloc[-1]["ma5"] == 58


@pytest.mark.parametrize("code", CODES)
def test_tw_fundamentals_never_use_china_adapter(code):
    manager, _, _ = manager_with_sources()
    manager._tw_institutional_fetcher = Mock()
    manager._tw_institutional_fetcher.get_institutional_net.return_value = None
    cfg = SimpleNamespace(enable_fundamental_pipeline=True, fundamental_cache_ttl_seconds=0,
                          fundamental_stage_timeout_seconds=2, fundamental_fetch_timeout_seconds=1,
                          fundamental_retry_max=0)
    bundle = {"status": "not_supported", "growth": {}, "earnings": {},
              "belong_boards": [], "source_chain": [], "errors": []}
    with patch("src.config.get_config", return_value=cfg), \
            patch.object(manager._yfinance_fundamental_adapter, "get_fundamental_bundle", return_value=bundle) as yahoo, \
            patch("data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_capital_flow") as china:
        context = manager.get_fundamental_context(code)
    assert context["market"] == "tw"
    yahoo.assert_called_once()
    china.assert_not_called()


def test_actions_stock_list_is_exported_without_changing_suffixes():
    import yaml

    workflow = yaml.safe_load((Path(__file__).parents[1] / ".github/workflows/00-daily-analysis.yml").read_text(encoding="utf-8"))
    step = next(s for s in workflow["jobs"]["analyze"]["steps"] if "STOCK_LIST_CONFIG" in s.get("env", {}))
    assert step["env"]["STOCK_LIST_CONFIG"] == "${{ vars.STOCK_LIST || secrets.STOCK_LIST }}"
    assert 'export STOCK_LIST="$STOCK_LIST_CONFIG"' in step["run"]


@pytest.mark.parametrize("code", CODES)
def test_tw_report_can_render_without_external_services(code):
    from tests.test_report_renderer import _make_result
    from src.services.report_renderer import render

    output = render("markdown", [_make_result(code=code, name="Taiwan issuer")], summary_only=False)
    assert output and code in output and "Taiwan issuer" in output
