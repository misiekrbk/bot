# gui.py
import sys
import asyncio
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QScrollArea,
    QFrame
)
from PySide6.QtCore import Qt, Slot, QTimer, QSize
from PySide6.QtGui import QFont
from qasync import QEventLoop, asyncSlot
from websocket_handler import BinanceWebSocketManager

class TradingGUI(QMainWindow):
    def __init__(self, optimizer, analyzer):
        super().__init__()
        self.optimizer = optimizer
        self.analyzer = analyzer
        self.running = False
        self.dark_mode = True
        self.price_labels = {}
        self.ws_manager = None
        
        self.init_ui()
        self.init_websocket()
        
        QTimer.singleShot(100, lambda: self.schedule_async(self.update_portfolio()))

    def init_ui(self):
        self.setWindowTitle("Crypto Trading Bot Pro")
        self.setGeometry(100, 100, 1280, 720)
        self.setMinimumSize(800, 600)

        # Główny kontener
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Górny panel - status
        self.status_bar = QWidget()
        status_layout = QHBoxLayout()
        self.status_bar.setLayout(status_layout)
        
        self.status_icon = QLabel("●")
        self.status_icon.setFixedSize(20, 20)
        self.status_text = QLabel("Status: Nieaktywny")
        self.balance_label = QLabel("Saldo: Ładowanie...")
        
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        status_layout.addWidget(self.balance_label)
        
        # Panel cen
        price_scroll = QScrollArea()
        price_widget = QWidget()
        self.price_layout = QHBoxLayout()
        price_widget.setLayout(self.price_layout)
        price_scroll.setWidget(price_widget)
        price_scroll.setWidgetResizable(True)
        price_scroll.setFixedHeight(80)

        # Konsola logów
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFont(QFont("Consolas", 10))

        # Panel sterowania
        control_frame = QFrame()
        control_layout = QHBoxLayout()
        control_frame.setLayout(control_layout)
        
        self.start_btn = QPushButton("Rozpocznij handel")
        self.start_btn.clicked.connect(self.start_trading)
        self.stop_btn = QPushButton("Zatrzymaj handel")
        self.stop_btn.clicked.connect(self.stop_trading)
        self.theme_btn = QPushButton("♻️ Motyw")
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        self.stop_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.theme_btn)

        # Składanie layoutu
        main_layout.addWidget(self.status_bar)
        main_layout.addWidget(price_scroll)
        main_layout.addWidget(self.log_console)
        main_layout.addWidget(control_frame)
        
        self.apply_theme()

    def init_websocket(self):
        self.ws_manager = BinanceWebSocketManager(self.optimizer.client)
        self.ws_manager.price_updated.connect(self.update_price_display)
        self.ws_manager.error_occurred.connect(lambda e: self.log(f"Błąd WS: {e}", error=True))
        
        # Rozpocznij WS dla głównych symboli
        symbols = self.analyzer.ticker_cache.valid_symbols[:10]
        self.schedule_async(self.ws_manager.start_symbol_ticker(symbols))
        
        # Dodaj etykiety cen
        for symbol in symbols:
            label = QLabel(f"{symbol}: ---")
            label.setObjectName(f"price_{symbol}")
            self.price_layout.addWidget(label)
            self.price_labels[symbol] = label

    @asyncSlot()
    async def start_trading(self):
        self.running = True
        self.toggle_controls(False)
        self.log("Rozpoczęto sesję handlową")
        
        try:
            while self.running:
                try:
                    market_data = await self.analyzer.analyze_market()
                    
                    allocations = self.optimizer.calculate_allocation(market_data)
                    orders = self.optimizer.generate_orders(allocations)
                    
                    self.log(f"Wygenerowano {len(orders)} zleceń")
                    self.optimizer.execute_orders(orders)
                    
                    await self.update_portfolio()
                    await asyncio.sleep(self.config.analysis_interval)
                
                except Exception as e:
                    self.log(f"Błąd iteracji: {str(e)}", error=True)
                    await asyncio.sleep(10)
        
        except Exception as e:
            self.log(f"Krytyczny błąd: {str(e)}", error=True)
        
        finally:
            self.stop_trading()

    @Slot()
    def stop_trading(self):
        self.running = False
        self.toggle_controls(True)
        self.log("Zatrzymano sesję handlową")

    def toggle_controls(self, enabled: bool):
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
        self.status_text.setText("Status: Aktywny" if not enabled else "Status: Nieaktywny")
        self.status_icon.setStyleSheet(
            "color: green" if not enabled else "color: red"
        )

    @asyncSlot()
    async def update_portfolio(self):
        try:
            portfolio = await asyncio.to_thread(self.optimizer.load_portfolio)
            total = sum(
                self.analyzer.ticker_cache.get_symbol_price(f"{asset}USDT") * amount 
                for asset, amount in portfolio.items()
            )
            self.balance_label.setText(f"Portfel: ${total:.2f}")
        except Exception as e:
            self.log(f"Błąd aktualizacji portfela: {str(e)}", error=True)

    @Slot(dict)
    def update_price_display(self, prices: dict):
        for symbol, price in prices.items():
            if symbol in self.price_labels:
                self.price_labels[symbol].setText(f"{symbol}: {price:.8f}")

    def log(self, message: str, error: bool = False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {'⚠️' if error else '✅'} {message}"
        self.log_console.append(log_entry)
        self.log_console.verticalScrollBar().setValue(
            self.log_console.verticalScrollBar().maximum()
        )

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget {
                    background-color: #2D2D2D;
                    color: #FFFFFF;
                    border: none;
                }
                QTextEdit {
                    background-color: #1E1E1E;
                }
                QPushButton {
                    background-color: #3A3A3A;
                    border: 1px solid #4A4A4A;
                    padding: 8px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #4A4A4A;
                }
                QScrollArea {
                    border: 1px solid #4A4A4A;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #FFFFFF;
                    color: #000000;
                    border: none;
                }
                QTextEdit {
                    background-color: #F0F0F0;
                }
                QPushButton {
                    background-color: #E0E0E0;
                    border: 1px solid #CCCCCC;
                    padding: 8px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #D0D0D0;
                }
                QScrollArea {
                    border: 1px solid #CCCCCC;
                }
            """)

    def schedule_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, asyncio.get_event_loop())

    def closeEvent(self, event):
        if self.ws_manager:
            self.schedule_async(self.ws_manager.close())
        event.accept()

def run_gui(optimizer, analyzer):
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        window = TradingGUI(optimizer, analyzer)
        window.show()
        
        with loop:
            loop.run_forever()
            
    except Exception as e:
        print(f"Krytyczny błąd GUI: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Przykładowa inicjalizacja (do testów)
    from config import load_config
    from exchange import BinanceAPIHandler, TickerCache
    from analyzer import CryptoAnalyzer
    from optimizer import PortfolioOptimizer
    
    config = load_config()
    client = BinanceAPIHandler(config)
    ticker_cache = TickerCache(client)
    analyzer = CryptoAnalyzer(client, None, ticker_cache, config, None, None)
    optimizer = PortfolioOptimizer(client, analyzer, config)
    
    run_gui(optimizer, analyzer)