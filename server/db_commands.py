import duckdb

con = duckdb.connect(database='./dados.db')

con.execute("""
CREATE TABLE
coordenadas (uid INTEGER, 
            latitude DOUBLE, 
            longitude DOUBLE, 
            timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
            )
""")
