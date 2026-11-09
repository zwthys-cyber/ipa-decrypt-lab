"""Run the production TF receiver regression in both public worker and release checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tests"))
from test_testflight_delivery import TFDeliveryReceiver
