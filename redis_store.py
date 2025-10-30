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
def create_customer_index():
    """Create RediSearch index for customers if not exists"""
    try:
        r.execute_command(
            "FT.CREATE", "idx:customers",
            "ON", "HASH",
            "PREFIX", "1", "customer:",
            "SCHEMA",
            "name", "TEXT", "PHONETIC", "dm:en"  # Define 'name' once with both TEXT and PHONETIC
        )
        print("✅ Created RediSearch index: idx:customers")
    except redis.ResponseError as e:
        if "Index already exists" in str(e):
            print("ℹ️ Customer index already exists, skipping")
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
            "name", "TEXT", "PHONETIC", "dm:en"  # Define 'name' once with both TEXT and PHONETIC
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
def load_customers_into_redis():
    """Load all customer names from SAP HANA into Redis"""
    conn = dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASS
    )
    cursor = conn.cursor()

    cursor.execute('SELECT "CardName" FROM "MJENGO_TEST_020725"."OCRD"')
    customers = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Clear old customer keys
    old_keys = r.keys("customer:*")
    if old_keys:
        r.delete(*old_keys)

    # Insert customers as HASH
    pipe = r.pipeline()
    for i, v in enumerate(customers):
        pipe.hset(f"customer:{i}", mapping={"name": v})
    pipe.execute()

    print(f"✅ Loaded {len(customers)} customers into Redis.")


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
@app.route("/api/customers")
def get_customers():
    query = request.args.get("search", "").strip()
    if not query:
        return jsonify([])

    # Use * for prefix search
    redis_query = f"{query}*"

    try:
        res = r.execute_command(
            "FT.SEARCH", "idx:customers", redis_query,
            "RETURN", "1", "name",
            "LIMIT", "0", "10"
        )
    except redis.ResponseError as e:
        return jsonify({"error": str(e)}), 500

    customer_names = []
    for i in range(1, len(res), 2):
        fields = res[i + 1]
        for j in range(0, len(fields), 2):
            if fields[j] == "name":
                customer_names.append(fields[j + 1])

    return jsonify(customer_names)


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
    create_customer_index()
    create_item_index()
    load_customers_into_redis()
    load_items_into_redis()
    app.run(host="0.0.0.0", port=5000, debug=False)
