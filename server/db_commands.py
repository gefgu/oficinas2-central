import duckdb

con = duckdb.connect(database='./dados/dados.db')

con.execute("""
CREATE TABLE IF NOT EXISTS 
coordenadas (uid INTEGER PRIMARY KEY, latitude DOUBLE, longitude DOUBLE, timestamp TIMESTAMP)
""")
