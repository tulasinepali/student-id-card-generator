import os
import sys

# Resolve root and backend directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')

# Add backend to Python path so 'config' and 'apps' are discoverable
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Expose WSGI application for Phusion Passenger (cPanel)
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
