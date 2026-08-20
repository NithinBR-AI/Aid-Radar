import sys
import os

# Ensure repo root is on the path so `from src.x import y` works on Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
