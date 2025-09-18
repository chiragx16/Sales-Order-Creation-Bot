from flask import Flask, request, jsonify, session
import redis
from redis.commands.search.field import TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Redis connection
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Create RediSearch index if not exists
try:
    r.ft("idx:vendors").info()
except:
    r.ft("idx:vendors").create_index(
        [TextField("name")],
        definition=IndexDefinition(prefix=["vendor:"], index_type=IndexType.HASH)
    )

# Vendor suggestions
@app.route("/api/vendors")
def get_vendors():
    query = request.args.get("search", "").strip()
    if not query:
        return jsonify([])

    # Search Redis using RediSearch
    res = r.ft("idx:vendors").search(f"@name:{query}*")
    return jsonify([doc.name for doc in res.docs])

# Step-based chatbot
@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()
    step = session.get("step", "vendor")

    if step == "vendor":
        session["vendor"] = user_input
        session["step"] = "invoice"
        return jsonify(reply=f"Got it! Vendor: {user_input}. Now, please provide the invoice number.")

    elif step == "invoice":
        session["invoice"] = user_input
        session["step"] = "date"
        return jsonify(reply="Please enter document date (YYYY-MM-DD).")

    elif step == "date":
        session["date"] = user_input
        session["items"] = []
        session["step"] = "items"
        return jsonify(reply="Enter item code, quantity, and price (comma separated). Type 'done' when finished.")

    elif step == "items":
        if user_input.lower() == "done":
            session["step"] = "confirm"
            summary = f"Vendor: {session['vendor']}\nInvoice: {session['invoice']}\nDate: {session['date']}\nItems: {session['items']}"
            return jsonify(reply=f"Summary:\n{summary}\nConfirm? (yes/no)")
        else:
            try:
                code, qty, price = user_input.split(",")
                session["items"].append({
                    "ItemCode": code.strip(),
                    "Quantity": int(qty.strip()),
                    "UnitPrice": float(price.strip())
                })
                return jsonify(reply="Item added. Add another or type 'done'.")
            except:
                return jsonify(reply="Invalid format. Please enter: itemcode, quantity, price")

    elif step == "confirm":
        if user_input.lower() == "yes":
            session.clear()
            return jsonify(reply="✅ Sales Order created successfully!")
        else:
            session.clear()
            return jsonify(reply="Cancelled. Let's start over.")

    return jsonify(reply="Something went wrong. Try again.")
