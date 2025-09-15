import duckdb

# Global connection (will be overridden in tests)
_default_con = duckdb.connect(database='./dados.db')
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
