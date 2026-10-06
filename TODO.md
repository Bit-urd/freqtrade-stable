# TODO

## Portfolio strategy follow-up

- [ ] Compare `Ma200BtcRegimeFullCyclePortfolioStrategy` and `Ma200BtcRegimeFullCycleCoreHoldStrategy` against an equal-weight buy-and-hold benchmark using the same pair list, start date, end date, starting capital, and fees.
- [ ] Reconcile open-trade end-of-period valuation with realized-trade profit so the comparison uses total portfolio equity for both strategies.
- [ ] Investigate bull-market entry lag and idle-cash periods; test earlier entries while keeping the BTC regime filter.
- [ ] Sweep the retained bullish core fraction (for example 25%, 50%, and 75%) and BTC bear-exit confirmation length; compare return and wallet drawdown across multiple market regimes.
- [ ] Check that the chosen settings remain useful out of sample before considering them for live trading.
