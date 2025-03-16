# telegram_handler.py
import logging
import aiohttp
from config import BotConfig
from typing import Dict, List

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, config: BotConfig):
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id
        
        if not self.chat_id.lstrip('-').isdigit():  # Nowa walidacja
            raise ValueError("Nieprawidłowy Chat ID")
        
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.session = aiohttp.ClientSession()

    async def send(self, message: str):
        try:
            async with self.session.post(
                f"{self.base_url}/sendMessage",
                params={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                }
            ) as response:
                await response.read()
        except Exception as e:
            logger.error(f"Błąd Telegram: {str(e)}")

    async def send_trade_alert(self, order: Dict):
        text = (
            f"🚨 **Nowa transakcja**\n"
            f"Symbol: `{order['symbol']}`\n"
            f"Typ: `{order['side']}`\n"
            f"Ilość: `{order['quantity']:.6f}`\n"
            f"Cena: `{order['price']:.2f}`"
        )
        await self.send(text)

    async def send_sentiment_report(self, sentiment_data: Dict, news_data: List[Dict]):
        report = "📈 **Raport Sentymentu Rynkowego**\n\n"
        report += "🔴 **Reddit**\n"
        for sub, data in sentiment_data.items():
            report += (
                f"- r/{sub}:\n"
                f"  😊 {data['positive']:.1%} | 😐 {data['neutral']:.1%} | 😠 {data['negative']:.1%}\n"
            )
        
        report += "\n📰 **Najważniejsze wiadomości**\n"
        for i, news in enumerate(news_data[:3], 1):
            report += (
                f"{i}. [{news['title']}]({news['url']})\n"
                f"   ⚖️ Sentyment: {'✅' if news['sentiment'] > 0 else '⚠️' if news['sentiment'] == 0 else '❌'}\n"
            )
        
        await self.send(report)

    async def close(self):
        await self.session.close()