import sys
from pathlib import Path

# Add project root directory to sys.path to resolve 'core' imports for Pylance and Pytest
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.config import settings
if not settings.secret_key:
    settings.secret_key = "test_secret_key_for_testing_12345"
if not settings.algorithm:
    settings.algorithm = "HS256"
if settings.access_token_expire_minutes == 0:
    settings.access_token_expire_minutes = 60
