# exchange.py
import logging
import time
from binance.client import Client
from cachetools import TTLCache
from utils import error_handler, DynamicRateLimiter

logger = logging.getLogger(__name__)

class BinanceAPIHandler:
    def __init__(self, config):
        self.client = Client(
            api_key=config.binance_api_key,
            api_secret=config.binance_api_secret,
            testnet=config.simulation_mode
        )
        self.ticker_cache = TTLCache(maxsize=100, ttl=60)
        self.account_cache = TTLCache(maxsize=1, ttl=60)
        self.limiter = DynamicRateLimiter(
            max_calls=config.api_rate_limit,
            window_seconds=config.api_rate_window
        )
        self.time_offset = 0
        self._synchronize_time()

    def _synchronize_time(self):
        try:
            server_time = self.client.get_server_time()['serverTime']
            local_time = int(time.time() * 1000)
            self.time_offset = server_time - local_time
        except Exception as e:
            logger.error(f"Błąd synchronizacji czasu: {str(e)}")

    @error_handler
    def get_symbol_price(self, symbol: str) -> float:
        if symbol not in self.ticker_cache:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            self.ticker_cache[symbol] = float(ticker['price'])
        return self.ticker_cache[symbol]

    @error_handler
    def get_account_balance(self) -> dict:
        if 'account' not in self.account_cache:
            self.account_cache['account'] = self.client.get_account()
        return self.account_cache['account']

    @error_handler
    def create_order(self, symbol: str, side: str, quantity: float, price: float):
        self.limiter.wait()
        timestamp = int(time.time() * 1000) + self.time_offset
        return self.client.create_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            timeInForce='GTC',
            quantity=quantity,
            price=price,
            params={'timestamp': timestamp}
        )

class TickerCache:
    def __init__(self, handler: BinanceAPIHandler):
        self.handler = handler
        self.symbols = []
        self.last_update = 0

    @error_handler
    def refresh_symbols(self):
        if time.time() - self.last_update > 3600:
            exchange_info = self.handler.client.get_exchange_info()
            self.symbols = [
                s['symbol'] for s in exchange_info['symbols']
                if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')
            ]
            self.last_update = time.time()
            logger.info("Zaktualizowano listę symboli")