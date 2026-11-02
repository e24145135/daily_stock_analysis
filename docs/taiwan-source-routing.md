# Taiwan source routing

Use explicit Yahoo symbols in `STOCK_LIST`: `2330.TW,2303.TW,6488.TWO,00878.TW`.
`.TW` identifies TWSE listings and `.TWO` identifies TPEx listings. Bare numeric
codes retain their existing market semantics.

Taiwan daily prices, realtime quotes and stock names use Yahoo Finance. Name
prefetch reads Yahoo metadata independently of price availability. Missing names
remain unavailable; failed Taiwan requests never fall back to China-only providers.
China-only bulk quote/K-line prefetch and chip-distribution lookup skip Taiwan.
Technical indicators are calculated locally from downloaded daily prices.
Yahoo daily downloads use `auto_adjust=False` for all supported markets: OHLC
is not dividend-adjusted, and `Adj Close` is not substituted for execution prices.
Yahoo may still normalize historical stock splits. Existing cached data is not
rewritten; new downloads can therefore differ from previously adjusted history.
Fundamentals retain the existing Yahoo adapter and official Taiwan institutional feed.

The daily Actions workflow resolves `vars.STOCK_LIST`, then `secrets.STOCK_LIST`,
then an existing runner `STOCK_LIST`, and finally `600519`. It exports the value
without stripping exchange suffixes. Repository configuration values and secret
contents do not need to be read to verify this contract.

Yahoo rate limits, outages and incomplete ETF metadata can still leave fields
unavailable. A full LLM report requires the existing model configuration; routing
tests do not require credentials or send notifications.
