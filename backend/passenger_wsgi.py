import os
import sys

# Resolve backend directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Expose WSGI application for Phusion Passenger (cPanel)
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
