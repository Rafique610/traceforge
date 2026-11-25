import os

TAX_RATE = float(os.getenv("TAX_RATE", "0.2"))
CACHE_HOST = os.getenv("CACHE_HOST", "localhost")
CACHE_PORT = int(os.getenv("CACHE_PORT", "6379"))
MAX_QTY = int(os.getenv("MAX_QTY", "100"))
