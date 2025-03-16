# utils.py
import logging
import time
import threading
from functools import wraps
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)
T = TypeVar('T')

class DynamicRateLimiter:
    def __init__(self, max_calls: int = 10, window_seconds: int = 5):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls = []
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            self.calls = [t for t in self.calls if t > now - self.window]
            
            if len(self.calls) >= self.max_calls:
                oldest = self.calls[0]
                wait_time = (oldest + self.window) - now
                
                if wait_time > 0:
                    logger.info(f"Oczekiwanie: {wait_time:.2f}s")
                    time.sleep(wait_time)
                    now = time.monotonic()
                    self.calls = [t for t in self.calls if t > now - self.window]
            
            self.calls.append(now)

def error_handler(func: Callable[..., T]) -> Callable[..., Optional[T]]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Błąd w {func.__name__}: {str(e)}", exc_info=True)
            return None
    return wrapper

def retry_on_exception(max_attempts: int = 3, timeout: float = 60.0) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    if time.time() - start_time > timeout:
                        raise TimeoutError("Przekroczono czas operacji")
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait = min(2 ** attempt, 10)
                    logger.warning(f"Próba {attempt+1}/{max_attempts} - Czekam {wait}s")
                    time.sleep(wait)
            
            raise last_exception if last_exception else RuntimeError("Nieznany błąd")
        return wrapper
    return decorator

@error_handler
def adjust_quantity(
    quantity: Union[float, str], 
    precision: int = 6
) -> float:
    try:
        decimal_value = Decimal(str(quantity))
        quantizer = Decimal('1.' + '0' * precision)
        return float(decimal_value.quantize(quantizer, rounding=ROUND_DOWN))
    except (ValueError, InvalidOperation) as e:
        logger.error(f"Błąd formatowania ilości: {str(e)}")
        raise  # Zmiana: zamiast return 0.0, rzucamy wyjątek

def convert_to_utc_timestamp(dt: str) -> int:
    from datetime import datetime
    try:
        return int(datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").timestamp()) * 1000
    except ValueError as e:
        logger.error(f"Błąd konwersji czasu: {str(e)}")
        raise ValueError("Nieprawidłowy format daty. Wymagany: YYYY-MM-DD HH:MM:SS") from e