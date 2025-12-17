import oracledb

# Thin mode (default)
oracledb.init_oracle_client = None

def get_connection():
    return oracledb.connect(
        user="SYSTEM",
        password="Ravi@123",
        dsn="localhost/XEPDB1"
    )
