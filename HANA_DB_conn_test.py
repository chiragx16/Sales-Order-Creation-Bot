from dotenv import load_dotenv

from hdbcli import dbapi

import os
import traceback

load_dotenv()

db_address = os.getenv("DB_ADDRESS")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

connection = dbapi.connect(
    address = db_address,
    port = db_port,
    user =  db_user,
    password = db_password 
)


try:

    cursor = connection.cursor()

    query = '''
        SELECT COLUMN_NAME, DATA_TYPE_NAME, IS_NULLABLE 
        FROM SYS.TABLE_COLUMNS
        WHERE SCHEMA_NAME = 'MJENGO_TEST_020725' 
        AND TABLE_NAME = 'OCRD'
        ORDER BY POSITION
    '''

    cursor.execute(query)

    schema_rows = cursor.fetchall()

    data = []

    for row in schema_rows:
        data.append(row)

    print("---- Table Structure ----")
    for row in data:
        print(f"Column={row[0]}, Data Type={row[1]}, Nullable={row[2]}")

except Exception as e:
    print("DATABASE Error : ", e)
    traceback.print_exc()

finally:
    cursor.close()
    connection.close()