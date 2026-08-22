import sys
from pathlib import Path

# Tests import the app package directly; no installed package, no path hacks
# scattered through every test file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
