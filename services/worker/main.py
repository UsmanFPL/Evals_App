import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery(
    'worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    """Handler for when the worker is ready."""
    logger.info("Worker is ready to process tasks")

@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Handler for when the worker is shutting down."""
    logger.info("Worker is shutting down")

# Import tasks after Celery app is configured
# from . import tasks

# Example task
@app.task(bind=True, name='evaluate_model')
def evaluate_model(self, run_id: str, model_name: str, prompt: str, input_data: dict):
    """
    Evaluate a model with the given input data.
    
    Args:
        run_id: Unique identifier for this evaluation run
        model_name: Name of the model to evaluate
        prompt: Prompt template to use
        input_data: Dictionary containing input data
        
    Returns:
        dict: Evaluation results
    """
    try:
        logger.info(f"Starting evaluation for run {run_id}")
        # TODO: Implement actual evaluation logic
        
        # Simulate work
        import time
        time.sleep(2)
        
        result = {
            "run_id": run_id,
            "status": "completed",
            "metrics": {
                "accuracy": 0.95,
                "latency": 2.1
            },
            "output": f"Processed input for run {run_id} with model {model_name}"
        }
        
        logger.info(f"Completed evaluation for run {run_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in evaluate_model for run {run_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds
