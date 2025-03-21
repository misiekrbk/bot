import logging
import backtrader as bt
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class CryptoStrategy(bt.Strategy):
    params = (
        ('rsi_period', 14),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('atr_period', 14),
        ('risk_per_trade', 0.02)
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI_SMA(self.data.close, period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            self.log(f"Zlecenie {order.exectype} {order.size} {order.data._name} @ {order.executed.price}")

    def next(self):
        if not self.position:
            if self.rsi < 30 and self.macd.macd > self.macd.signal:
                size = self.broker.getvalue() * self.p.risk_per_trade / self.atr[0]
                self.buy(size=size)
        else:
            if self.rsi > 70 or self.macd.macd < self.macd.signal:
                self.sell()

    def log(self, txt):
        dt = self.datas[0].datetime.date(0)
        logger.info(f"{dt} - {txt}")

def run_backtest(data: pd.DataFrame, strategy=CryptoStrategy):
    cerebro = bt.Cerebro(stdstats=False)
    
    data['date'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('date', inplace=True)
    
    feed = bt.feeds.PandasData(
        dataname=data,
        datetime=None,
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4
    )
    cerebro.adddata(feed)
    
    cerebro.addstrategy(strategy)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    logger.info(f'Początkowy kapitał: {cerebro.broker.getvalue():.2f}')
    cerebro.run()
    logger.info(f'Końcowy kapitał: {cerebro.broker.getvalue():.2f}')
    
    return cerebro