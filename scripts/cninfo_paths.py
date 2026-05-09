import os
import tempfile

DATA_DIR = os.environ.get("CNINFO_DATA_DIR") or (
    "/tmp/cninfo_watch" if os.name != "nt" else os.path.join(tempfile.gettempdir(), "cninfo_watch")
)
HISTORY_DIR = os.path.join(DATA_DIR, "history")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
FILINGS_DIR = os.path.join(DATA_DIR, "filings")
