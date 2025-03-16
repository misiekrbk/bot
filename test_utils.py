import pytest
import time
import threading
from unittest.mock import MagicMock
from utils import DynamicRateLimiter, adjust_quantity
from optimizer import PortfolioOptimizer  # Dodany import

def test_rate_limiter_concurrent():
    limiter = DynamicRateLimiter(max_calls=5, window_seconds=1)
    results = []
    lock = threading.Lock()

    def worker():
        start = time.time()
        limiter.wait()
        with lock:
            results.append(time.time() - start)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert max(results) - min(results) <= 2.0

def test_adjust_quantity_edge_cases():
    assert adjust_quantity("123.456789", 0) == 123.0
    assert adjust_quantity(0.00000001, 8) == 0.00000001
    with pytest.raises(ValueError):
        adjust_quantity("invalid", 2)

def test_optimizer_zero_balance():
    mock_client = MagicMock()
    mock_client.get_account.return_value = {'balances': [{'asset': 'USDT', 'free': '0.0'}]}
    
    class MockConfig:
        simulation_mode = True
        max_trade_usd = 1000
    
    optimizer = PortfolioOptimizer(mock_client, MagicMock(), MockConfig())
    orders = optimizer.generate_orders({'BTCUSDT': 1000})
    assert len(orders) == 0