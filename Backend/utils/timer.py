import time
import functools
from utils.logger import get_uuid_logger


def timer_decorator(func):
    """Decorator: Calculates function execution time and logs it."""

    @functools.wraps(func)
    def wrapper(state, config=None):
        # Get logger
        uuid = state.get("uuid", "unknown")
        logger = get_uuid_logger(uuid)

        # Record start time
        start_time = time.time()
        logger.info(f"[ TIMER ] Starting {func.__name__}...")

        try:
            # Execute original function
            result = func(state, config)

            # Calculate execution time
            end_time = time.time()
            execution_time = end_time - start_time

            # Record completion time
            logger.info(
                f"[ TIMER ] {func.__name__} completed in {execution_time:.2f} seconds"
            )

            # Add execution time to state
            if isinstance(result, dict):
                if "execution_times" not in result:
                    result["execution_times"] = {}
                result["execution_times"][func.__name__] = execution_time

            return result

        except Exception as e:
            # Calculate execution time (even on error)
            end_time = time.time()
            execution_time = end_time - start_time

            # Log error and execution time
            logger.error(
                f"[ TIMER ] {func.__name__} failed after {execution_time:.2f} seconds: {str(e)}"
            )

            # Add execution time to state (even on error)
            if isinstance(state, dict):
                if "execution_times" not in state:
                    state["execution_times"] = {}
                state["execution_times"][func.__name__] = execution_time

            # Re-raise the exception
            raise

    return wrapper


def log_total_execution_time(state, logger=None):
    """Logs the total execution time."""
    if not logger:
        uuid = state.get("uuid", "unknown")
        logger = get_uuid_logger(uuid)

    execution_times = state.get("execution_times", {})
    if execution_times:
        total_time = sum(execution_times.values())
        logger.info(f"[ TIMER ] Total execution time: {total_time:.2f} seconds")
        logger.info(f"[ TIMER ] Breakdown: {execution_times}")
    else:
        logger.info("[ TIMER ] No execution times recorded")
