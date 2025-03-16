# optimizer.py
import logging
import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List
from utils import DynamicRateLimiter

logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    def __init__(self, client, analyzer, config):
        self.client = client
        self.analyzer = analyzer
        self.config = config
        self.limiter = self._get_limiter()
        self.risk_manager = None

    def _get_limiter(self):
        if self.analyzer and hasattr(self.analyzer, 'api_handler'):
            return self.analyzer.api_handler.limiter
        return DynamicRateLimiter(
            max_calls=self.config.api_rate_limit,
            window_seconds=self.config.api_rate_window
        )

    def set_risk_manager(self, risk_manager):
        self.risk_manager = risk_manager

    def load_portfolio(self) -> Dict[str, float]:
        try:
            self.limiter.wait()
            account = self.client.get_account()
            return {
                asset['asset']: float(asset['free'])
                for asset in account['balances']
                if float(asset['free']) > 0
            }
        except Exception as e:
            logger.error(f"Błąd ładowania portfela: {str(e)}")
            return {}

    def calculate_allocation(self, predictions: pd.DataFrame) -> Dict[str, float]:
        if predictions.empty:
            logger.warning("Brak danych predykcyjnych! Używam równomiernej alokacji")
            return {
                symbol: self.config.max_trade_usd / 5 
                for symbol in self.analyzer.ticker_cache.symbols[:5]
            }
        
        if 'score' not in predictions.columns:
            logger.error("DataFrame nie zawiera kolumny 'score'")
            return {}

        total_score = predictions['score'].sum()
        if total_score <= 0:
            logger.error("Suma wyników <= 0. Ustawiam domyślne alokacje.")
            return {row['symbol']: self.config.max_trade_usd / len(predictions) for _, row in predictions.iterrows()}

        return {
            row['symbol']: (row['score'] / total_score) * self.config.max_trade_usd
            for _, row in predictions.iterrows()
        }

    def generate_orders(self, allocations: Dict[str, float]) -> List[Dict]:
        if not self.risk_manager:
            raise RuntimeError("RiskManager nie został zainicjalizowany")

        orders = []
        portfolio = self.load_portfolio()
        usdt_balance = portfolio.get('USDT', 0.0)
        valid_symbols = self.analyzer.ticker_cache.symbols
        
        risk_orders = self.risk_manager.check_positions()
        orders.extend(risk_orders)

        for symbol, amount in allocations.items():
            if symbol not in valid_symbols:
                logger.warning(f"Symbol {symbol} nie jest dostępny. Pomijanie...")
                continue
                
            if amount <= 0 or symbol in [o['symbol'] for o in risk_orders]:
                continue

            try:
                self.limiter.wait()
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])
                
                info = self.client.get_symbol_info(symbol)
                step_size = next(
                    f['stepSize'] for f in info['filters']
                    if f['filterType'] == 'LOT_SIZE'
                )
                
                precision = Decimal(step_size).normalize().as_tuple().exponent * -1
                quantity = amount / price
                adjusted_qty = self._adjust_quantity(quantity, precision)
                
                if usdt_balance >= amount:
                    orders.append({
                        'symbol': symbol,
                        'side': 'BUY',
                        'quantity': adjusted_qty,
                        'price': price
                    })
                    self.risk_manager.update_position(symbol, adjusted_qty, price)
                    usdt_balance -= amount

            except Exception as e:
                logger.error(f"Błąd generowania zlecenia {symbol}: {str(e)}")

        return orders

    def _adjust_quantity(self, quantity: float, precision: int) -> float:
        try:
            return float(
                Decimal(str(quantity)).quantize(
                    Decimal('1.' + '0' * precision),
                    rounding=ROUND_DOWN
                )
            )
        except Exception as e:
            logger.error(f"Błąd dostosowania ilości: {str(e)}")
            return 0.0

    def execute_orders(self, orders: List[Dict]) -> None:
        if self.config.simulation_mode:
            logger.info("SYMULACJA ZAMÓWIEŃ:")
            for order in orders:
                logger.info(
                    f"{order['side']} {order['symbol']} "
                    f"{order['quantity']} @ {order['price']}"
                )
            return

        for order in orders:
            try:
                self.limiter.wait()
                self.client.create_order(
                    symbol=order['symbol'],
                    side=order['side'],
                    type='MARKET',
                    quantity=order['quantity']
                )
                logger.info(f"WYKONANO: {order['side']} {order['symbol']}")
            except Exception as e:
                logger.error(f"Błąd wykonania zlecenia: {str(e)}")

    def generate_emergency_orders(self) -> List[Dict]:
        portfolio = self.load_portfolio()
        orders = []
        
        for asset, amount in portfolio.items():
            if asset == 'USDT' or amount <= 0:
                continue
            
            symbol = f"{asset}USDT"
            try:
                self.limiter.wait()
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])
                
                info = self.client.get_symbol_info(symbol)
                step_size = next(
                    f['stepSize'] for f in info['filters']
                    if f['filterType'] == 'LOT_SIZE'
                )
                
                precision = Decimal(step_size).normalize().as_tuple().exponent * -1
                adjusted_qty = self._adjust_quantity(amount, precision)
                
                orders.append({
                    'symbol': symbol,
                    'side': 'SELL',
                    'quantity': adjusted_qty,
                    'price': price
                })
                
            except Exception as e:
                logger.error(f"Błąd generowania zlecenia awaryjnego {symbol}: {str(e)}")
        
        return orders