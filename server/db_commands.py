import duckdb

def create_tables(con):
    """Create trajectory and visit tables if they do not exist"""
    con.execute("""
    CREATE TABLE
    trajectory (
        uid INTEGER, 
        latitude DOUBLE, 
        longitude DOUBLE, 
        timestamp TIMESTAMP,
        trip_number INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    con.execute("""
    CREATE TABLE
    visit (
        uid INTEGER, 
        trip_number INTEGER,
        arrive_time TIMESTAMP,
        depart_time TIMESTAMP,
        latitude DOUBLE,
        longitude DOUBLE,
        purpose VARCHAR,
        mode_of_transport VARCHAR,
        validated BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
    )
    """)

if __name__ == "__main__":
    con = duckdb.connect(database='./dados.db')
    create_tables(con)