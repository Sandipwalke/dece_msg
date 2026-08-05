"""DeceMSG - Decentralized Messaging Platform."""
from decemsg.main import app, run_cli
from decemsg.deploy import deploy, run_server

__version__ = "0.1.0"
__all__ = ["app", "run_cli", "deploy", "run_server"]
