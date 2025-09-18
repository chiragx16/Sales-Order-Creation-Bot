# flask_chatbot_simple.py
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Temporary storage for user input (for demonstration, resets on server restart)
user_data = {}

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.json
    action = data.get("action")

    # Start step
    if action == "start":
        return jsonify(
            reply="Great! Let's create a sales order. Please provide the vendor name:",
            next_action="vendor_name"
        )

    # Vendor name step
    if action == "vendor_name":
        vendor_name = data.get("vendor_name")
        if not vendor_name:
            return jsonify(reply="Please provide a valid vendor name.", next_action="vendor_name")
        user_data["vendor_name"] = vendor_name
        return jsonify(
            reply=f"Perfect! Vendor recorded: {vendor_name}. Now, please provide invoice number:",
            next_action="invoice"
        )

    # Invoice number step
    if action == "invoice":
        invoice_number = data.get("invoice_number")
        if not invoice_number:
            return jsonify(reply="Please provide a valid invoice number.", next_action="invoice")
        user_data["invoice_number"] = invoice_number
        return jsonify(
            reply=f"Got it! Invoice recorded: {invoice_number}. Now, please enter document date (YYYY-MM-DD):",
            next_action="date"
        )

    # Document date step
    if action == "date":
        document_date = data.get("document_date")
        if not document_date:
            return jsonify(reply="Please provide a valid document date.", next_action="date")
        user_data["document_date"] = document_date
        summary = (
            f"All set! Here's what we got:\n"
            f"Vendor: {user_data.get('vendor_name')}\n"
            f"Invoice: {user_data.get('invoice_number')}\n"
            f"Date: {user_data.get('document_date')}\n"
            "You can now confirm or restart."
        )
        return jsonify(reply=summary, next_action="confirm")

    # Default fallback
    return jsonify(reply="Something went wrong. Please start again.", next_action="start")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
