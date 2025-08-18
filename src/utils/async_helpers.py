"""
Async utilities and helpers for better async patterns
"""
import asyncio
import functools
from typing import Any, Callable, Coroutine, List, Optional, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_in_executor(executor: Optional[ThreadPoolExecutor] = None):
    """
    Decorator to run synchronous functions in a thread pool executor
    
    Usage:
    @run_in_executor()
    def sync_function():
        # synchronous code
        return result
    
    # Can now be awaited
    result = await sync_function()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor, 
                functools.partial(func, *args, **kwargs)
            )
        return wrapper
    return decorator


async def gather_with_concurrency(
    limit: int, 
    *coroutines: Coroutine[Any, Any, T]
) -> List[T]:
    """
    Run coroutines with a concurrency limit
    
    Args:
        limit: Maximum number of concurrent operations
        *coroutines: Coroutines to run
        
    Returns:
        List of results in the same order as input coroutines
    """
    semaphore = asyncio.Semaphore(limit)
    
    async def sem_coro(coro):
        async with semaphore:
            return await coro
    
    return await asyncio.gather(*[sem_coro(coro) for coro in coroutines])


async def retry_async(
    func: Callable[..., Coroutine[Any, Any, T]],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    Retry an async function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry on
        
    Returns:
        Result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries")
                raise e
            
            wait_time = delay * (backoff ** attempt)
            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {wait_time:.2f}s: {str(e)}"
            )
            await asyncio.sleep(wait_time)
    
    # This should never be reached, but just in case
    if last_exception:
        raise last_exception


async def timeout_after(seconds: float, coro: Coroutine[Any, Any, T]) -> T:
    """
    Run a coroutine with a timeout
    
    Args:
        seconds: Timeout in seconds
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If the coroutine times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {seconds} seconds")
        raise


class AsyncBatch:
    """
    Utility for batching async operations
    
    Usage:
    async with AsyncBatch(batch_size=10) as batch:
        for item in items:
            batch.add(process_item(item))
        results = await batch.execute()
    """
    
    def __init__(self, batch_size: int = 10, concurrency_limit: Optional[int] = None):
        self.batch_size = batch_size
        self.concurrency_limit = concurrency_limit or batch_size
        self.operations: List[Coroutine] = []
        self.results: List[Any] = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.operations:
            # Execute any remaining operations
            await self._execute_batch(self.operations)
    
    def add(self, coro: Coroutine):
        """Add a coroutine to the batch"""
        self.operations.append(coro)
        
        # Auto-execute when batch is full
        if len(self.operations) >= self.batch_size:
            asyncio.create_task(self._execute_and_clear())
    
    async def _execute_and_clear(self):
        """Execute current batch and clear operations"""
        if self.operations:
            batch_results = await self._execute_batch(self.operations)
            self.results.extend(batch_results)
            self.operations.clear()
    
    async def _execute_batch(self, operations: List[Coroutine]) -> List[Any]:
        """Execute a batch of operations with concurrency control"""
        if self.concurrency_limit:
            return await gather_with_concurrency(self.concurrency_limit, *operations)
        else:
            return await asyncio.gather(*operations)
    
    async def execute(self) -> List[Any]:
        """Execute all remaining operations and return all results"""
        await self._execute_and_clear()
        return self.results


class AsyncContextManager:
    """
    Base class for async context managers with proper cleanup
    """
    
    async def __aenter__(self):
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        
        # Handle exceptions during cleanup
        if exc_type is not None:
            logger.error(f"Exception in async context: {exc_type.__name__}: {exc_val}")
        
        return False  # Don't suppress exceptions
    
    async def setup(self):
        """Override this method to implement setup logic"""
        pass
    
    async def cleanup(self):
        """Override this method to implement cleanup logic"""
        pass


def async_cached_property(func):
    """
    Decorator for async cached properties
    
    Usage:
    class MyClass:
        @async_cached_property
        async def expensive_property(self):
            # expensive async operation
            return result
    
    # Usage
    obj = MyClass()
    result = await obj.expensive_property  # Computed once
    result = await obj.expensive_property  # Cached result
    """
    cache_attr = f'_cached_{func.__name__}'
    
    @functools.wraps(func)
    async def wrapper(self):
        if not hasattr(self, cache_attr):
            result = await func(self)
            setattr(self, cache_attr, result)
        return getattr(self, cache_attr)
    
    return wrapper


async def run_periodic_task(
    coro_func: Callable[[], Coroutine[Any, Any, None]],
    interval: float,
    max_iterations: Optional[int] = None
):
    """
    Run a coroutine function periodically
    
    Args:
        coro_func: Async function to run periodically
        interval: Interval between runs in seconds
        max_iterations: Maximum number of iterations (None for infinite)
    """
    iteration = 0
    
    while max_iterations is None or iteration < max_iterations:
        try:
            await coro_func()
        except Exception as e:
            logger.error(f"Error in periodic task: {e}")
        
        await asyncio.sleep(interval)
        iteration += 1
