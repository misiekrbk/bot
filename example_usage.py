import asyncio
from config import load_config
from exchange import BinanceAPIHandler, TickerCache
from analyzer import CryptoAnalyzer
from optimizer import PortfolioOptimizer
from risk_manager import RiskManager

async def main():
    config = load_config()
    
    # Inicjalizacja klienta Binance
    client = Client(
        api_key=config.binance_api_key,
        api_secret=config.binance_api_secret,
        testnet=config.simulation_mode
    )
    
    # Inicjalizacja komponentów
    ticker_cache = TickerCache(client)
    analyzer = CryptoAnalyzer(client, None, ticker_cache, config, None, None)
    optimizer = PortfolioOptimizer(client, analyzer, config)
    risk_manager = RiskManager(optimizer)
    
    # Cykl handlowy
    while True:
        market_data = await analyzer.analyze_market()
        allocations = optimizer.calculate_allocation(market_data)
        orders = optimizer.generate_orders(allocations)
        optimizer.execute_orders(orders)
        await asyncio.sleep(config.analysis_interval)

if __name__ == "__main__":
    asyncio.run(main())