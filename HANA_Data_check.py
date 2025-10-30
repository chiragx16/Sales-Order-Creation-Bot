from hdbcli import dbapi
from dotenv import load_dotenv
import os
import traceback
import json
import decimal
import datetime

load_dotenv()

db_address = os.getenv("DB_ADDRESS")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


connection = dbapi.connect(
    address=db_address,
    port=db_port,
    user=db_user,
    password=db_password
)


try:

    cursor = connection.cursor()

    query = '''
        SELECT TOP 10 * FROM VCERP_TEST.OCRD;
    '''

    cursor.execute(query)

    records = cursor.fetchall()
    columns = [col[0] for col in cursor.description]

    data = []
    for row in records:
        row_dict = {}
        for col, val in zip(columns, row):
            # Handle non-JSON types
            if isinstance(val, decimal.Decimal):
                val = float(val)  # or str(val) if you prefer
            elif isinstance(val, (datetime.date, datetime.datetime)):
                val = val.isoformat()  # converts to "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS"
            row_dict[col] = val
        data.append(row_dict)

    # Convert to JSON string
    json_data = json.dumps(data, indent=2, ensure_ascii=False)

    print(json_data)

    with open("OCRD.json", "w", encoding="utf-8") as file:
        file.write(json_data)

except Exception as e:
    print("DATABASE Error : " , e)
    traceback.print_exc()