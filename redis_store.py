from flask import Flask, request, jsonify
from flask_cors import CORS
from hdbcli import dbapi  
from dotenv import load_dotenv
import redis
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- CONFIG ---
HANA_HOST = os.getenv("DB_ADDRESS")
HANA_PORT = os.getenv("DB_PORT")
HANA_USER = os.getenv("DB_USER")
HANA_PASS = os.getenv("DB_PASSWORD")

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def load_vendors_into_redis():
    """Load all vendor names from SAP HANA into Redis (set or sorted set)."""
    # Connect to SAP HANA using hdbcli
    conn = dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASS
    )
    cursor = conn.cursor()

    # Fetch all vendor names from the "OCRD" table in schema "MJENGO_TEST_020725"
    query = '''
        SELECT "CardName" FROM "MJENGO_TEST_020725"."OCRD"
    '''
    cursor.execute(query)
    vendors = [row[0] for row in cursor.fetchall()]

    conn.close()

    # Store vendor names in Redis (using a Redis Set for uniqueness)
    r.delete("vendors")  # clear old cache
    for v in vendors:
        r.sadd("vendors", v)

    print(f"✅ Loaded {len(vendors)} vendors into Redis.")


@app.route("/api/vendors")
def get_vendors():
    query = request.args.get("search", "").lower()
    if not query:
        return jsonify([])

    # Fetch all vendors (could be optimized with RedisSearch if needed)
    vendors = list(r.smembers("vendors"))
    results = [v for v in vendors if query in v.lower()]
    return jsonify(results[:10])  # return top 10 matches

if __name__ == "__main__":
    load_vendors_into_redis()
    app.run(host="0.0.0.0", port=5000, debug=True)
