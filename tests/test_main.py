import pytest
from unittest.mock import patch, MagicMock
import main
import sys

@pytest.fixture
def mock_components():
    with patch('main.trade_logger') as mock_logger, \
         patch('main.data_manager') as mock_data, \
         patch('main.ensemble') as mock_ensemble, \
         patch('main.ai_validator') as mock_validator, \
         patch('main.risk_manager') as mock_risk, \
         patch('main.mt5_connector') as mock_mt5, \
         patch('main.trade_manager') as mock_trade:
         
        # Set default successful behaviors
        mock_data.start.return_value = True
        mock_data.get_market_snapshot.return_value = {"status": "OK", "price_data": {"close": 150.0}}
        
        mock_validator.check_ollama_connection.return_value = True
        mock_validator.validate.return_value = {"validated": True}
        
        mock_mt5.connect.return_value = True
        # Make place_order and send_order return a dict with ticket
        mock_mt5.place_order.return_value = {"ticket": 12345}
        mock_mt5.send_order.return_value = {"ticket": 12345}
            
        mock_ensemble.get_ensemble_signal.return_value = {"final_signal": "BUY"}
        
        mock_risk.evaluate.return_value = {"decision": "APPROVED", "lot_size": 0.1, "stop_loss": 100, "take_profit": 200}
        
        yield {
            "logger": mock_logger,
            "data": mock_data,
            "ensemble": mock_ensemble,
            "validator": mock_validator,
            "risk": mock_risk,
            "mt5": mock_mt5,
            "trade": mock_trade
        }

def test_initialize_system_success(mock_components):
    assert main.initialize_system() is True
    mock_components["logger"].initialize_db.assert_called_once()
    mock_components["data"].start.assert_called_once()
    mock_components["validator"].check_ollama_connection.assert_called_once()
    mock_components["mt5"].connect.assert_called_once()
    mock_components["trade"].start_monitoring.assert_called_once()

def test_initialize_system_failure_data(mock_components):
    mock_components["data"].start.return_value = False
    assert main.initialize_system() is False

def test_run_signal_cycle_snapshot_error(mock_components):
    snapshot = {"status": "ERROR"}
    assert main.run_signal_cycle(snapshot) is None

def test_run_signal_cycle_no_trade(mock_components):
    mock_components["ensemble"].get_ensemble_signal.return_value = {"final_signal": "NO_TRADE"}
    assert main.run_signal_cycle({"status": "OK"}) is None

def test_run_signal_cycle_validation_fails(mock_components):
    mock_components["validator"].validate.return_value = {"validated": False}
    assert main.run_signal_cycle({"status": "OK"}) is None

def test_run_signal_cycle_risk_blocked(mock_components):
    mock_components["risk"].evaluate.return_value = {"decision": "BLOCKED"}
    assert main.run_signal_cycle({"status": "OK"}) is None

def test_run_signal_cycle_success(mock_components):
    order = main.run_signal_cycle({"status": "OK", "price_data": {"close": 150.0}})
    assert order is not None
    assert order["ticket"] == 12345
    mock_components["logger"].log_execution.assert_called_once()

@patch('main.time.sleep', return_value=None)
def test_main_loop_exception_handling(mock_sleep, mock_components):
    # Make snapshot raise an exception on first call, then stop the loop on the second
    def snapshot_side_effect():
        if not hasattr(snapshot_side_effect, 'called'):
            snapshot_side_effect.called = True
            raise Exception("Test Error")
        main.running = False
        return {"status": "OK"}
        
    mock_components["data"].get_market_snapshot.side_effect = snapshot_side_effect
    
    with patch('sys.exit'):
        main.main()
            
    # The first call raised Exception, the loop caught it and called sleep
    assert mock_sleep.called

def test_shutdown(mock_components):
    with patch('sys.exit') as mock_exit:
        main.shutdown(None, None)
        mock_components["trade"].stop_monitoring.assert_called_once()
        mock_components["data"].stop.assert_called_once()
        mock_components["mt5"].disconnect.assert_called_once()
        mock_exit.assert_called_once_with(0)
