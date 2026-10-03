"""Single source of configuration; no model or cloud service required."""
import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
WEIGHTS = {'Required skills':35, 'Preferred skills':10, 'Text similarity':20,
           'Title fit':15, 'Experience fit':10, 'Preference fit':10}
MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 20000
RETENTION = 24 * 3600
DB_PATH = Path(os.getenv('R2J_DB_PATH', str(ROOT / 'runtime' / 'resume2job.db')))
VERSION = '2.0.0'
