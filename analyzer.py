# analyzer.py
import logging
import pandas as pd
import numpy as np
import aiohttp
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from typing import Dict, Optional, List
from sentiment import SentimentAnalyzer

logger = logging.getLogger(__name__)

class CryptoAnalyzer:
    def __init__(
        self,
        binance_client,
        reddit: Optional[object],
        ticker_cache: object,
        config: object,
        api_handler: object,
        cryptopanic_api_key: Optional[str] = None
    ):
        self.client = binance_client
        self.reddit = reddit
        self.ticker_cache = ticker_cache
        self.config = config
        self.api_handler = api_handler
        self.cryptopanic_api_key = cryptopanic_api_key
        self.sentiment_analyzer = SentimentAnalyzer(config)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def analyze_market(self) -> pd.DataFrame:
        try:
            symbols = self.ticker_cache.symbols[:100]
            results = []
            
            for symbol in symbols:
                try:
                    df = self.get_historical_data(symbol, '1h')
                    if df.empty:
                        continue
                    
                    indicators = self.calculate_indicators(df)
                    if not indicators:
                        self.logger.warning(f"Brak wskaźników dla {symbol}")
                        continue
                    
                    score = self.calculate_score(indicators)
                    results.append({
                        'symbol': symbol,
                        'price': df['close'].iloc[-1],
                        'score': score,
                        **indicators
                    })
                except Exception as e:
                    self.logger.error(f"Błąd przetwarzania {symbol}: {str(e)}")
                    continue
            
            if not results:
                return pd.DataFrame(columns=['symbol', 'price', 'score', 'rsi', 'macd', 'adx', 'bb_percent'])
            
            df = pd.DataFrame(results)
            df = self.process_results(df)
            
            if self.config.enable_news and not self.config.simulation_mode:
                await self.add_sentiment_data(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Krytyczny błąd analizy: {str(e)}")
            return pd.DataFrame(columns=['symbol', 'price', 'score'])

    def get_historical_data(self, symbol: str, interval: str) -> pd.DataFrame:
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=100
            )
            return self.parse_klines(klines)
        except Exception as e:
            self.logger.error(f"Błąd danych {symbol}: {str(e)}")
            return pd.DataFrame()

    def parse_klines(self, klines: list) -> pd.DataFrame:
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        try:
            rsi = RSIIndicator(df['close'], window=14).rsi().iloc[-1]
            macd = MACD(df['close']).macd_diff().iloc[-1]
            adx = ADXIndicator(df['high'], df['low'], df['close']).adx().iloc[-1]
            bb = BollingerBands(df['close'], window=20, window_dev=2)
            bb_percent = self.calculate_bb_percent(df, bb)
            
            return {
                'rsi': round(rsi, 2),
                'macd': round(macd, 4),
                'adx': round(adx, 2),
                'bb_percent': round(bb_percent, 2)
            }
        except Exception as e:
            self.logger.error(f"Błąd wskaźników: {str(e)}")
            return {}

    def calculate_score(self, indicators: Dict[str, float]) -> float:
        return (
            0.4 * (1 - indicators['rsi']/100) + 
            0.3 * indicators['macd'] + 
            0.3 * indicators['bb_percent']
        )

    def calculate_bb_percent(self, df: pd.DataFrame, bb: BollingerBands) -> float:
        hband = bb.bollinger_hband().iloc[-1]
        lband = bb.bollinger_lband().iloc[-1]
        current_close = df['close'].iloc[-1]
        bb_diff = hband - lband
        return (current_close - lband) / bb_diff if bb_diff != 0 else 0.0

    async def add_sentiment_data(self, df: pd.DataFrame) -> None:
        try:
            reddit_data = await self.analyze_reddit_sentiment(["CryptoCurrency", "Bitcoin"])
            news_data = await self.analyze_cryptopanic_news()
            
            for _, row in df.iterrows():
                coin = row['symbol'].replace('USDT', '')
                df.loc[df['symbol'] == row['symbol'], 'reddit_sentiment'] = \
                    reddit_data.get(coin, {}).get('positive', 0)
            
            news_score = sum([n['sentiment'] for n in news_data])/len(news_data) if news_data else 0
            df['news_sentiment'] = news_score
            
            df['score'] = df['score'] * (1 - self.config.news_weight) + \
                          (df['reddit_sentiment'] + df['news_sentiment']) * self.config.news_weight
            
        except Exception as e:
            self.logger.error(f"Błąd integracji sentymentu: {str(e)}")

    def process_results(self, results: list) -> pd.DataFrame:
        return results.sort_values('score', ascending=False).reset_index(drop=True)