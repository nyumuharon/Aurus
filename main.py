"""
Aurus - Main System Entry Point
Initializes all layers, runs the main event loop, and coordinates components.
"""
import time
import logging
import signal as sys_signal
import sys
from config import settings

# Import components
from src.monitoring import trade_logger
from src.data import data_manager
from src.models import ensemble
from src.validator import ai_validator
from src.risk import risk_manager
from src.execution import mt5_connector, trade_manager

running = False

def initialize_system():
    """Run full startup sequence."""
    try:
        logging.basicConfig(
            filename=settings.SYSTEM_LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info("Starting Aurus Initialization")

        # 2. Initialize trade journal DB
        trade_logger.initialize_db()

        # 3. Initialize risk manager DB
        risk_manager.initialize_db()

        # 4. Initialize execution DB
        if hasattr(mt5_connector, '_initialize_db'):
            mt5_connector._initialize_db()

        # 5. Start Data Manager
        if not data_manager.start():
            logging.critical("Data Manager failed to start")
            return False

        
        # 6. Check Ollama connection
        if not ai_validator.check_ollama_connection():
            logging.critical("Ollama not connected")
            return False

        # 7. Connect to MT5
        if not mt5_connector.connect():
            logging.critical("MT5 not connected")
            return False

        # 8. Start trade monitor
        trade_manager.start_monitoring()

        return True

    except Exception as e:
        logging.critical(f"System initialization error: {e}")
        return False

def run_signal_cycle(snapshot):
    """Execute one full signal detection cycle."""
    if not snapshot or snapshot.get("status") == "ERROR":
        return None

    # 2 - Get ensemble signal
    signal = ensemble.get_ensemble_signal()
    trade_logger.log_signal(signal)
    if signal.get("final_signal") == "NO_TRADE":
        return None

    # 3 - Validate with AI
    validation = ai_validator.validate(signal, snapshot)
    trade_logger.log_validation(validation)
    if not validation.get("validated"):
        return None

    # 4 - Risk check
    risk = risk_manager.evaluate(validation, snapshot)
    trade_logger.log_risk_decision(risk)
    if risk.get("decision") == "BLOCKED":
        return None

    # 5 - Execute
    order = None
    try:
        if hasattr(mt5_connector, 'send_order'):
            order = mt5_connector.send_order(risk)
        else:
            order_signal = signal.get("final_signal")
            order = mt5_connector.place_order(
                signal=order_signal,
                lot_size=risk.get("lot_size", 0.0),
                entry_price=risk.get("entry_price", snapshot.get("price_data", {}).get("close", 0.0)),
                stop_loss=risk.get("stop_loss", 0.0),
                take_profit=risk.get("take_profit", 0.0)
            )
        
        if order:
            trade_logger.log_execution(order)
            return order
    except Exception as e:
        logging.error(f"Execution error: {e}")
    
    return None

def shutdown(signum, frame):
    """Handle graceful shutdown."""
    global running
    logging.info("Shutdown signal received")
    running = False
    
    trade_manager.stop_monitoring()
    data_manager.stop()
    mt5_connector.disconnect()
    
    logging.info("Aurus shutdown complete")
    sys.exit(0)

def main():
    """Entry point — initialize then loop."""
    global running

    sys_signal.signal(sys_signal.SIGINT, shutdown)
    sys_signal.signal(sys_signal.SIGTERM, shutdown)

    if not initialize_system():
        logging.critical("Failed to initialize Aurus")
        sys.exit(1)
        
    running = True
    logging.info("Aurus is running")

    while running:
        try:
            snapshot = data_manager.get_market_snapshot()
            if snapshot.get("status") == "ERROR":
                time.sleep(settings.MAIN_LOOP_INTERVAL_SECONDS)
                continue
                
            run_signal_cycle(snapshot)
        except Exception as e:
            logging.critical(f"Main loop error: {e}")

        time.sleep(settings.MAIN_LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
