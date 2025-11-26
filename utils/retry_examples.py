"""
Examples demonstrating the unified retry utilities.

This file shows various use cases for the retry decorators and helpers.
"""
from utils.retry import retry, retry_with_context, RetryableOperation
from core.logger import app_log


# =============================================================================
# EXAMPLE 1: Simple function retry with decorator
# =============================================================================

@retry(max_attempts=3, log_prefix="Database Query")
def fetch_user_data(user_id: str):
    """Fetch user data with automatic retry on failure."""
    # Simulated database call
    result = database.query(f"SELECT * FROM users WHERE id = {user_id}")
    if not result:
        return False  # Triggers retry
    return result


# =============================================================================
# EXAMPLE 2: Retry with specific exception handling
# =============================================================================

@retry(
    max_attempts=3,
    catch=(ConnectionError, TimeoutError),  # Only retry these
    exclude=(ValueError,),  # Never retry these
    log_prefix="API Call"
)
def call_external_api(endpoint: str):
    """Call external API with retry on connection issues only."""
    response = requests.get(endpoint)
    if response.status_code >= 500:
        raise ConnectionError(f"Server error: {response.status_code}")
    return response.json()


# =============================================================================
# EXAMPLE 3: Custom retry callback
# =============================================================================

def on_retry_handler(attempt: int, max_attempts: int, error: Exception):
    """Custom callback invoked on each retry."""
    app_log(f"Custom handler: Backing off before attempt {attempt + 1}")
    time.sleep(2 ** attempt)  # Exponential backoff


@retry(max_attempts=5, on_retry=on_retry_handler)
def flaky_operation():
    """Operation with exponential backoff on retry."""
    return external_service.ping()


# =============================================================================
# EXAMPLE 4: Context-based retry (state machines)
# =============================================================================

class ProcessingContext:
    def __init__(self):
        self.retry_count = 0
        self.max_retries = 3
        self.data = None


def process_with_state(context: ProcessingContext):
    """Process with state-aware retry logic."""
    try:
        context.data = perform_processing()
        return True
    except Exception as e:
        app_log(f"Processing error: {e}")

        # Check if we can retry
        if retry_with_context(context):
            # Reset and try again
            context.data = None
            return process_with_state(context)
        else:
            # Exhausted retries
            return False


# =============================================================================
# EXAMPLE 5: Context manager style
# =============================================================================

def deploy_application():
    """Deploy application with retry context manager."""
    for attempt in range(3):
        with RetryableOperation("Application Deployment", max_attempts=3) as op:
            # Perform deployment steps
            build_artifacts()
            upload_to_server()
            restart_services()

            # Mark as successful
            op.success()
            break  # Exit retry loop


# =============================================================================
# EXAMPLE 6: Combining orchestrator with retry
# =============================================================================

class CustomOrchestrator:
    """Example showing orchestrator integration."""

    def __init__(self):
        self.results = []

    def execute_workflow(self, workflow_func, workflow_name: str):
        """Execute workflow with unified retry logic."""

        @retry(max_attempts=2, log_prefix=workflow_name)
        def wrapped_workflow():
            return workflow_func()

        result = wrapped_workflow()
        self.results.append((workflow_name, result))
        return result


# =============================================================================
# EXAMPLE 7: Conditional retry logic
# =============================================================================

def should_retry_on_error(error: Exception) -> bool:
    """Custom logic to decide if error is retryable."""
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    if isinstance(error, ValueError) and "temporary" in str(error):
        return True
    return False


@retry(
    max_attempts=3,
    catch=(Exception,),
    log_prefix="Smart Retry"
)
def smart_operation():
    """Operation with smart retry logic."""
    try:
        return perform_critical_task()
    except Exception as e:
        if not should_retry_on_error(e):
            # Don't retry, mark as failure
            return False
        raise  # Re-raise to trigger retry


# =============================================================================
# USAGE COMPARISON: Before and After
# =============================================================================

# BEFORE: Manual retry logic scattered everywhere
def old_style_operation():
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            result = do_something()
            if result:
                return result
            retry_count += 1
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                return None
    return None


# AFTER: Clean, declarative retry with decorator
@retry(max_attempts=3)
def new_style_operation():
    return do_something()
