import logging
import threading
from flask import current_app
from app.agents.report_reader import ReportReaderAgent

logger = logging.getLogger(__name__)

def process_report_background_task(app_context, report_id: str, patient_id: str):
    """
    Run the ReportReaderAgent graph in a background thread 
    so the API request doesn't block.
    """
    app_context.push()
    try:
        logger.info("Starting background processing for report %s", report_id)
        
        agent = ReportReaderAgent()
        
        # Build initial state for the report reader graph
        initial_state = {
            "report_id": report_id,
            "patient_id": patient_id,
            "messages": [], # No conversational messages for this graph
            "intent": "report_analysis",
            "context": {},
            "error": None,
        }
        
        # Invoke the graph
        result = agent.invoke(initial_state)
        
        if result.get("error"):
            logger.error("Background task for report %s failed: %s", report_id, result.get("error"))
        else:
            logger.info("Background task for report %s completed successfully", report_id)
            
    except Exception as e:
        logger.exception("Fatal error in process_report_background_task: %s", e)
    finally:
        app_context.pop()

def trigger_report_processing(report_id: str, patient_id: str):
    """Spawns a new thread to process the report"""
    # Grab the current app context to pass to the thread
    app_ctx = current_app._get_current_object().app_context()
    
    thread = threading.Thread(
        target=process_report_background_task,
        args=(app_ctx, report_id, patient_id)
    )
    thread.daemon = True
    thread.start()
    return True
