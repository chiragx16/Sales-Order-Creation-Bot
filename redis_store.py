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


# -----------------------------
# INDEX CREATION
# -----------------------------
def create_vendor_index():
    """Create RediSearch index for vendors if not exists"""
    try:
        r.execute_command(
            "FT.CREATE", "idx:vendors",
            "ON", "HASH",
            "PREFIX", "1", "vendor:",
            "SCHEMA",
            "name", "TEXT",
            "TEXT_PHONETIC", "EN"  # optional phonetic or ngram for better partial match
        )
        print("✅ Created RediSearch index: idx:vendors")
    except redis.ResponseError as e:
        if "Index already exists" in str(e):
            print("ℹ️ Vendor index already exists, skipping")
        else:
            raise


def create_item_index():
    """Create RediSearch index for items if not exists"""
    try:
        r.execute_command(
            "FT.CREATE", "idx:items",
            "ON", "HASH",
            "PREFIX", "1", "item:",
            "SCHEMA",
            "name", "TEXT",
            "TEXT_PHONETIC", "EN"  # optional phonetic or ngram for better partial match
        )
        print("✅ Created RediSearch index: idx:items")
    except redis.ResponseError as e:
        if "Index already exists" in str(e):
            print("ℹ️ Item index already exists, skipping")
        else:
            raise


# -----------------------------
# LOAD DATA FROM HANA
# -----------------------------
def load_vendors_into_redis():
    """Load all vendor names from SAP HANA into Redis"""
    conn = dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASS
    )
    cursor = conn.cursor()

    cursor.execute('SELECT "CardName" FROM "MJENGO_TEST_020725"."OCRD"')
    vendors = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Clear old vendor keys
    old_keys = r.keys("vendor:*")
    if old_keys:
        r.delete(*old_keys)

    # Insert vendors as HASH
    pipe = r.pipeline()
    for i, v in enumerate(vendors):
        pipe.hset(f"vendor:{i}", mapping={"name": v})
    pipe.execute()

    print(f"✅ Loaded {len(vendors)} vendors into Redis.")


def load_items_into_redis():
    """Load all item names from SAP HANA into Redis"""
    conn = dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASS
    )
    cursor = conn.cursor()

    cursor.execute('SELECT "ItemName" FROM "MJENGO_TEST_020725"."OITM"')
    items = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Clear old item keys
    old_keys = r.keys("item:*")
    if old_keys:
        r.delete(*old_keys)

    # Insert items as HASH
    pipe = r.pipeline()
    for i, itm in enumerate(items):
        pipe.hset(f"item:{i}", mapping={"name": itm})
    pipe.execute()

    print(f"✅ Loaded {len(items)} items into Redis.")


# -----------------------------
# API ENDPOINTS
# -----------------------------
@app.route("/api/vendors")
def get_vendors():
    query = request.args.get("search", "").strip()
    if not query:
        return jsonify([])

    # Use * for prefix search
    redis_query = f"{query}*"

    try:
        res = r.execute_command(
            "FT.SEARCH", "idx:vendors", redis_query,
            "RETURN", "1", "name",
            "LIMIT", "0", "10"
        )
    except redis.ResponseError as e:
        return jsonify({"error": str(e)}), 500

    vendor_names = []
    for i in range(1, len(res), 2):
        fields = res[i + 1]
        for j in range(0, len(fields), 2):
            if fields[j] == "name":
                vendor_names.append(fields[j + 1])

    return jsonify(vendor_names)


@app.route("/api/items")
def get_items():
    query = request.args.get("search", "").strip()
    if not query:
        return jsonify([])
    
    # Use * for prefix search
    redis_query = f"{query}*"

    try:
        res = r.execute_command(
            "FT.SEARCH", "idx:items", redis_query,
            "RETURN", "1", "name",
            "LIMIT", "0", "10"
        )
    except redis.ResponseError as e:
        return jsonify({"error": str(e)}), 500

    item_names = []
    for i in range(1, len(res), 2):
        fields = res[i + 1]
        for j in range(0, len(fields), 2):
            if fields[j] == "name":
                item_names.append(fields[j + 1])

    return jsonify(item_names)


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    create_vendor_index()
    create_item_index()
    load_vendors_into_redis()
    load_items_into_redis()
    app.run(host="0.0.0.0", port=5000, debug=True)
