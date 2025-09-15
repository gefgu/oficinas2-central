import duckdb

con = duckdb.connect(database='./dados.db')

con.execute("""
CREATE TABLE
trajectory (
    uid INTEGER, 
    latitude DOUBLE, 
    longitude DOUBLE, 
    timestamp TIMESTAMP,
    trip_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated BOOLEAN DEFAULT FALSE
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
)
""")
