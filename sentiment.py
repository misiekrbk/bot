# sentiment.py
import logging
import aiohttp
import asyncpraw
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self, config):
        self.config = config
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("ElKulako/cryptobert")
            self.model = AutoModelForSequenceClassification.from_pretrained("ElKulako/cryptobert")
        except Exception as e:  # Nowy blok try-except
            logger.critical(f"Błąd ładowania modelu: {str(e)}")
            raise
        self.reddit = None
        self.session = None

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        if not self.config.simulation_mode:
            self.reddit = asyncpraw.Reddit(
                client_id=self.config.reddit_client_id,
                client_secret=self.config.reddit_client_secret,
                user_agent="crypto-bot/1.0"
            )

    async def analyze_reddit_comments(self, subreddits: List[str]) -> Dict[str, Dict]:
        results = {}
        try:
            for sub in subreddits:
                subreddit = await self.reddit.subreddit(sub)
                comments = []
                async for comment in subreddit.comments(limit=100):
                    comments.append(comment.body)
                
                sentiment = self._analyze_batch(comments)
                results[sub] = sentiment
        except Exception as e:
            logger.error(f"Błąd Reddit: {str(e)}")
        return results

    def _analyze_batch(self, texts: List[str]) -> Dict[str, float]:
        positive = neutral = negative = 0
        for text in texts:
            score = self._analyze_text(text)
            if score > 0.6:
                positive += 1
            elif score < 0.4:
                negative += 1
            else:
                neutral += 1
        total = positive + neutral + negative
        return {
            "positive": positive/total if total > 0 else 0,
            "neutral": neutral/total if total > 0 else 0,
            "negative": negative/total if total > 0 else 0
        }

    def _analyze_text(self, text: str) -> float:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return torch.sigmoid(outputs.logits).item()

    async def analyze_cryptopanic_news(self) -> List[Dict]:
        try:
            url = "https://cryptopanic.com/api/v1/posts/"
            params = {
                "auth_token": self.config.cryptopanic_api_key,
                "currencies": "BTC,ETH",
                "kind": "news"
            }
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                return self._process_news(data.get("results", []))
        except Exception as e:
            logger.error(f"Błąd CryptoPanic: {str(e)}")
            return []

    def _process_news(self, news: List[Dict]) -> List[Dict]:
        processed = []
        for item in news:
            sentiment = self._analyze_text(item.get("title", "") + " " + item.get("description", ""))
            processed.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "source": item.get("source", {}).get("title"),
                "published_at": item.get("published_at"),
                "sentiment": sentiment
            })
        return processed

    async def close(self):
        if self.session:
            await self.session.close()
        if self.reddit:
            await self.reddit.close()