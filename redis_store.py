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


def create_vendor_index():
    """Create RediSearch index for vendors if not exists"""
    try:
        r.execute_command(
            "FT.CREATE", "idx:vendors",
            "ON", "HASH",
            "PREFIX", "1", "vendor:",
            "SCHEMA",
            "name", "TEXT"
        )
        print("✅ Created RediSearch index: idx:vendors")
    except redis.ResponseError as e:
        if "Index already exists" in str(e):
            print("ℹ️ Index already exists, skipping")
        else:
            raise


def load_vendors_into_redis():
    """Load all vendor names from SAP HANA into Redis (as hashes)"""
    # Connect to SAP HANA
    conn = dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASS
    )
    cursor = conn.cursor()

    # Fetch vendors
    query = 'SELECT "CardName" FROM "MJENGO_TEST_020725"."OCRD"'
    cursor.execute(query)
    vendors = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Clear old vendor keys
    old_keys = r.keys("vendor:*")
    if old_keys:
        r.delete(*old_keys)

    # Insert vendors as HASH with `name` field
    pipe = r.pipeline()
    for i, v in enumerate(vendors):
        pipe.hset(f"vendor:{i}", mapping={"name": v})
    pipe.execute()

    print(f"✅ Loaded {len(vendors)} vendors into Redis.")


@app.route("/api/vendors")
def get_vendors():
    query = request.args.get("search", "").strip()
    if not query:
        return jsonify([])

    # Full-text search with RediSearch, return only 'name'
    redis_query = f"%{query}%"  # fuzzy match
    try:
        res = r.execute_command(
            "FT.SEARCH", "idx:vendors", redis_query,
            "RETURN", "1", "name",  # return only 'name'
            "LIMIT", "0", "10"
        )
    except redis.ResponseError as e:
        return jsonify({"error": str(e)}), 500

    # Parse results: FT.SEARCH returns [count, key1, [field, value], key2, [field, value], ...]
    vendor_names = []
    for i in range(1, len(res), 2):
        fields = res[i+1]
        for j in range(0, len(fields), 2):
            if fields[j] == "name":
                vendor_names.append(fields[j+1])

    return jsonify(vendor_names)



if __name__ == "__main__":
    create_vendor_index()
    load_vendors_into_redis()
    app.run(host="0.0.0.0", port=5000, debug=True)
