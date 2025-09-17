import duckdb
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Determine database file based on environment
def get_db_file():
    production_mode = os.getenv('PRODUCTION_MODE', 'true').lower() == 'true'
    db_file_path = './dados.db' if production_mode else './dados_test.db'
    # print(f"Using database file: {db_file_path}")
    return db_file_path

# Global connection (will be overridden in tests)
_default_con = duckdb.connect(database=get_db_file())
_test_con = None

def get_db():
    """Dependency to get database connection"""
    if _test_con is not None:
        return _test_con
    return _default_con

def set_test_db(con):
    """Set test database connection"""
    global _test_con
    _test_con = con

def clear_test_db():
    """Clear test database connection"""
    global _test_con
    _test_con = None