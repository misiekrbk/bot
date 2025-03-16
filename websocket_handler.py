# websocket_handler.py
import logging
import asyncio
from binance import AsyncClient, BinanceSocketManager
from cachetools import TTLCache
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class BinanceWebSocketManager(QObject):
    price_updated = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, client: AsyncClient):
        super().__init__()
        self.client = client
        self.bm = BinanceSocketManager(client)
        self.sockets = []
        self.price_cache = TTLCache(maxsize=500, ttl=60)
        self.running = False

    async def start_symbol_ticker(self, symbols: list):
        self.running = True
        max_retries = 3  # Nowy mechanizm
        for symbol in symbols:
            retries = 0
            while retries < max_retries and self.running:
                try:
                    ts = self.bm.symbol_ticker_socket(symbol)
                    self.sockets.append(ts)
                    async with ts as tsc:
                        while self.running:
                            msg = await tsc.recv()
                            self._process_message(msg, symbol)
                    break
                except Exception as e:
                    logger.error(f"Błąd WebSocket ({symbol}): {str(e)}. Próba {retries+1}/{max_retries}")
                    retries += 1
                    await asyncio.sleep(5 ** retries)
        self.running = False

    def _process_message(self, message, symbol):
        try:
            if 'e' in message and message['e'] == '24hrTicker':
                price = float(message['c'])
                self.price_cache[symbol] = price
                self.price_updated.emit({symbol: price})
        except KeyError as e:
            self.error_occurred.emit(f"Błędny format wiadomości: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Błąd przetwarzania: {str(e)}")

    async def close(self):
        self.running = False
        for ts in self.sockets:
            await ts.__aexit__(None, None, None)
        self.sockets.clear()