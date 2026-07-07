import os
import sys

# testapp importeerbaar maken voor DJANGO_SETTINGS_MODULE=testapp.settings_test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests"))
