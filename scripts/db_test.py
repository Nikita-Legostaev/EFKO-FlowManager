from dotenv import load_dotenv
from sqlalchemy import create_engine
import pandas as pd

load_dotenv()

SERVER = 'mskbz-dms'
DATABASE = 'Products'

connection_string = (
    f'mssql+pyodbc://{SERVER}/{DATABASE}'
    f'?trusted_connection=yes&driver=SQL+Server'
)

engine = create_engine(connection_string)

try:
    with engine.connect() as conn:
        query = 'SELECT 1 AS test'
        result = pd.read_sql_query(query, conn)
        print("Соединение успешно!")
        print(result)
except Exception as e:
    print(f"Ошибка подключения: {e}")