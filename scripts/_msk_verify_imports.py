import sys

sys.path.insert(0, "/opt/targpt")
from bot_core import robokassa

print("configured", robokassa.is_configured())
print("receipt", robokassa.receipt_enabled())
print("recurring", robokassa.recurring_enabled())
