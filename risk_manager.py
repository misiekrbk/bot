# risk_manager.py
import logging
from typing import Dict, Optional
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, optimizer, analyzer, config):
        self.optimizer = optimizer
        self.analyzer = analyzer
        self.config = config
        self.initial_balance = None
        self.current_balance = None
        self.entry_prices = {}
        self.open_positions = {}

    def check_portfolio_health(self, current_value: float) -> bool:
        if not self.initial_balance:
            self.initial_balance = current_value
            self.current_balance = current_value
            return True
            
        drawdown = (self.initial_balance - current_value) / self.initial_balance
        self.current_balance = current_value
        
        if drawdown >= self.config.max_drawdown:
            logger.warning(f"Wykryto spadek wartości: {drawdown:.2%}")
            self.trigger_safety_measures()
            return False
        return True

    def trigger_safety_measures(self):
        logger.info("Aktywacja protokołu bezpieczeństwa")
        emergency_orders = self.optimizer.generate_emergency_orders()
        self.optimizer.execute_orders(emergency_orders)

    def dynamic_stop_loss(self, symbol: str) -> float:
        volatility = self.analyzer.calculate_volatility(symbol)
        current_price = Decimal(self.optimizer.client.get_symbol_ticker(symbol=symbol)['price'])
        return float(current_price * (Decimal(1) - Decimal(volatility) * Decimal(2)))

    def dynamic_take_profit(self, symbol: str) -> Optional[float]:
        try:
            entry_price = self.entry_prices.get(symbol)
            if not entry_price:
                return None
                
            volatility = self.analyzer.calculate_volatility(symbol)
            tp_price = entry_price * (Decimal(1) + Decimal(volatility) * Decimal(3.5))
            return float(tp_price)
        except Exception as e:
            logger.error(f"Błąd TP {symbol}: {str(e)}")
            return None

    def update_position(self, symbol: str, quantity: float, price: float):
        self.entry_prices[symbol] = Decimal(str(price))
        self.open_positions[symbol] = {
            'quantity': Decimal(str(quantity)),
            'entry_price': Decimal(str(price))
        }

    def check_positions(self) -> list:
        orders = []
        for symbol, position in self.open_positions.items():
            current_price = Decimal(self.optimizer.client.get_symbol_ticker(symbol=symbol)['price'])
            
            sl_level = Decimal(str(self.dynamic_stop_loss(symbol)))
            if current_price <= sl_level:
                orders.append(self._create_close_order(symbol, "STOP_LOSS"))
                
            tp_level = self.dynamic_take_profit(symbol)
            if tp_level is not None and current_price >= Decimal(str(tp_level)):
                orders.append(self._create_close_order(symbol, "TAKE_PROFIT"))
        
        return orders

    def _create_close_order(self, symbol: str, reason: str) -> dict:
        return {
            'symbol': symbol,
            'side': 'SELL',
            'quantity': float(self.open_positions[symbol]['quantity']),
            'price': float(self.optimizer.client.get_symbol_ticker(symbol=symbol)['price']),
            'type': reason
        }