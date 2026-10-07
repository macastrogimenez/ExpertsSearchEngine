import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "ese-thesis.cxuc8cw6iqno.eu-north-1.rds.amazonaws.com"),
    "dbname": os.getenv("DB_NAME", "ESE"),
    "user": os.getenv("DB_USER", "macastrog"),
    "password": os.getenv("DB_PASSWORD", "Syptix-bycwar-wyqxe0"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "sslmode": os.getenv("DB_SSLMODE", "require"),
}