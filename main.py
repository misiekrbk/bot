# main.py
import logging
logging.basicConfig(level=logging.DEBUG)
import os
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from functools import partial
import asyncpraw
from dotenv import load_dotenv
from binance.client import Client
from config import load_config
from exchange import BinanceAPIHandler, TickerCache
from analyzer import CryptoAnalyzer
from optimizer import PortfolioOptimizer
from risk_manager import RiskManager

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["PYTHONWARNINGS"] = "ignore::FutureWarning"

load_dotenv()

class CryptoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crypto Trading Bot Pro")
        self.geometry("1280x720")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.loop = asyncio.new_event_loop()
        self.executor = threading.Thread(target=self._run_loop, daemon=True)
        self.executor.start()
        
        self.running = False
        self.reddit_client = None
        self.analyzer = None
        self.optimizer = None
        self.risk_manager = None
        self.mode_var = tk.StringVar(value="test")
        self.config = load_config()
        
        self.create_widgets()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def schedule_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(pady=10)
        
        ttk.Label(mode_frame, text="Tryb pracy:").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Testowy", variable=self.mode_var, value="test").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Produkcyjny", variable=self.mode_var, value="prod").pack(side=tk.LEFT, padx=5)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_icon = ttk.Label(status_frame, text="●", foreground="red")
        self.status_icon.pack(side=tk.LEFT, padx=5)
        self.status_text = ttk.Label(status_frame, text="Niezainicjalizowany")
        self.status_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        self.console = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Consolas', 10), height=25)
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.tag_config('success', foreground='green')
        self.console.tag_config('error', foreground='red')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        self.start_btn = ttk.Button(button_frame, text="Start", command=lambda: self.schedule_async(self._async_start()), state=tk.NORMAL)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_analysis, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

    async def _async_start(self):
        if not self.mode_var.get():
            self.show_error("Wybierz tryb pracy!")
            return

        try:
            self.config.mode = self.mode_var.get()
            await self.initialize_components()
            await self._async_start_analysis()
        except Exception as e:
            self.show_error(f"Błąd inicjalizacji: {str(e)}")

    async def initialize_components(self):
        try:
            await self.async_update_status("Inicjalizacja klienta Binance...", 10)
            self.api_handler = BinanceAPIHandler(self.config)
            self.binance_client = self.api_handler.client

            await self.async_update_status("Łączenie z Reddit...", 30)
            self.reddit_client = await self.create_reddit_client()

            await self.async_update_status("Inicjalizacja TickerCache...", 50)
            self.ticker_cache = TickerCache(self.api_handler)

            await self.async_update_status("Inicjalizacja analizatora...", 60)
            self.analyzer = CryptoAnalyzer(
                binance_client=self.binance_client,
                reddit=self.reddit_client,
                ticker_cache=self.ticker_cache,
                config=self.config,
                api_handler=self.api_handler,
                cryptopanic_api_key=os.getenv("CRYPTOPANIC_API_KEY")
            )

            await self.async_update_status("Inicjalizacja optymalizatora...", 70)
            self.optimizer = PortfolioOptimizer(
                client=self.binance_client,
                analyzer=self.analyzer,
                config=self.config
            )

            await self.async_update_status("Inicjalizacja menedżera ryzyka...", 80)
            self.risk_manager = RiskManager(
                optimizer=self.optimizer,
                analyzer=self.analyzer,
                config=self.config
            )

            self.optimizer.set_risk_manager(self.risk_manager)

            await self.async_update_status("Gotowy do działania", 100, "green")
            self.start_btn.config(state=tk.NORMAL)

        except Exception as e:
            self.show_error(f"Błąd inicjalizacji: {str(e)}")
            self.start_btn.config(state=tk.DISABLED)
            raise

    async def create_reddit_client(self):
        if not self.config.enable_news or self.config.mode == "test":
            return None

        try:
            return await asyncpraw.Reddit(
                client_id=os.getenv("REDDIT_CLIENT_ID"),
                client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
                user_agent="crypto-bot/1.0",
                timeout=30
            ).__aenter__()
        except Exception as e:
            self.show_error(f"Błąd połączenia Reddit: {str(e)}")
            return None

    async def _async_start_analysis(self):
        try:
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.console.delete(1.0, tk.END)

            while self.running:
                await self.async_update_status("Analiza rynku...", 20)
                market_data = await self.analyzer.analyze_market()
                
                await self.async_update_status("Generowanie zleceń...", 50)
                allocations = self.optimizer.calculate_allocation(market_data)
                orders = self.optimizer.generate_orders(allocations)
                
                await self.async_update_status("Wykonywanie zleceń...", 80)
                self.optimizer.execute_orders(orders)
                
                await self.async_update_status("Cykl zakończony", 100, "green")
                await asyncio.sleep(self.config.analysis_interval)

        except Exception as e:
            self.show_error(f"Błąd analizy: {str(e)}")
        finally:
            self.running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def stop_analysis(self):
        self.running = False
        self.update_status("Analiza przerwana", 0, "red")
        self.log("Analiza przerwana przez użytkownika", tag='error')

    def update_status(self, text: str, progress: int = 0, color: str = "black"):
        self.status_text.config(text=text)
        self.status_icon.config(foreground=color)
        self.progress['value'] = progress

    async def async_update_status(self, text: str, progress: int = 0, color: str = "black"):
        self.after(0, partial(self.update_status, text, progress, color))
        await asyncio.sleep(0)

    def log(self, message: str, tag: str = None):
        self.console.insert(tk.END, message, tag)
        self.console.see(tk.END)

    def show_error(self, message: str):
        self.log(f"\n⛔ {message}\n", 'error')
        messagebox.showerror("Błąd", message)

    async def on_close(self):
        if self.reddit_client:
            await self.reddit_client.__aexit__(None, None, None)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()

if __name__ == "__main__":
    app = CryptoApp()
    app.mainloop()