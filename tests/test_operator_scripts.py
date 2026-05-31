from pathlib import Path


def test_operator_dashboard_scripts_manage_pid_logs_and_health() -> None:
    start_script = Path("scripts/start_operator_dashboard.ps1").read_text(encoding="utf-8")
    stop_script = Path("scripts/stop_operator_dashboard.ps1").read_text(encoding="utf-8")
    serve_script = Path("scripts/serve_operator_dashboard.py").read_text(encoding="utf-8")

    assert "operator_dashboard.pid" in start_script
    assert "operator_dashboard.out.log" in start_script
    assert "operator_dashboard.err.log" in start_script
    assert "serve_operator_dashboard.py" in start_script
    assert "/health" in start_script
    assert "/operator" in start_script
    assert "Start-Process" in start_script
    assert "-WindowStyle Hidden" in start_script

    assert "operator_dashboard.pid" in stop_script
    assert "Stop-Process" in stop_script
    assert "Remove-Item" in stop_script

    assert "uvicorn.run" in serve_script
    assert "systematic_trading.app:app" in serve_script
    assert "os.getpid()" in serve_script
    assert "ST_AUTOMATION_ENABLED" in serve_script
    assert "--disable-automation" in serve_script
