"""Lets the tests import the scripts they are testing as plain modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
