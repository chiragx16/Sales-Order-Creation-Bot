from flask import Flask, request, jsonify
from flask_cors import CORS
from hdbcli import dbapi  # SAP HANA client
from dotenv import load_dotenv
import os

load_dotenv()

db_address = os.getenv("DB_ADDRESS")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


app = Flask(__name__)
CORS(app)

# Temporary storage for user input (for demonstration, resets on server restart)
user_data = {
    "use_case": None,
    "sales_order": {},   # store all sales order related data
    "invoice": {},       # store all invoice related data
    "other": {}          # etc
}


# --- HANA Database connection function ---
def get_vendor_code_from_db(vendor_name):
    try:
        # Connect to HANA (replace with your credentials)
        conn = dbapi.connect(
            address=db_address,  # HANA server hostname or IP
            port=db_port,           # HANA port (default: 30015 for SQL)
            user=db_user,
            password=db_password
        )
        cursor = conn.cursor()

        # Example query (adjust table & column names for your system)
        query = '''
        SELECT T0."CardCode"
        FROM "MJENGO_TEST_020725"."OCRD" T0
        WHERE T0."CardName" = ?
        '''

        # cursor.execute("SELECT T0.[CardCode] FROM OCRD T0 WHERE T0.[CardName] = %s", (vendor_name,))
        cursor.execute(query, (vendor_name,))
        result = cursor.fetchone()
        print("Result : ", result)
        cursor.close()
        conn.close()

        if result:
            return result[0]  # vendor_code
        else:
            return None
    except Exception as e:
        print("HANA DB Error:", e)
        return None



# --- HANA Database connection function for item ---
def get_item_details_from_db(item_name):
    try:
        conn = dbapi.connect(
            address=db_address,
            port=db_port,
            user=db_user,
            password=db_password
        )
        cursor = conn.cursor()

        query = '''
        SELECT T0."ItemCode", T0."ItemName", T0."PriceUnit"
        FROM "MJENGO_TEST_020725"."OITM" T0
        WHERE T0."ItemName" = ?
        '''
        cursor.execute(query, (item_name,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return {
                "ItemCode": result[0],
                "ItemName": result[1],
                "PriceUnit": result[2]
            }
        else:
            return None
    except Exception as e:
        print("HANA DB Error (Item):", e)
        return None





def sales_order_flow(action, data):
    flow_data = user_data["sales_order"]

    if action == "start":
        return jsonify(
            reply="Great! Let's create a Sales Order. Please provide the vendor name:",
            next_action="vendor_name"
        )

    # Vendor name step
    if action == "vendor_name":
        vendor_name = data.get("vendor_name")
        if not vendor_name:
            return jsonify(reply="Please provide a valid vendor name.", next_action="vendor_name")

        flow_data["vendor_name"] = vendor_name

        # --- Fetch vendor code from HANA DB ---
        vendor_code = get_vendor_code_from_db(vendor_name)
        if vendor_code:
            flow_data["vendor_code"] = vendor_code
            vendor_msg = f"Perfect! Vendor recorded: {vendor_name} (Code: {vendor_code})."
        else:
            vendor_msg = f"Vendor '{vendor_name}' not found in database."

        print(user_data)
        return jsonify(
            reply=f"{vendor_msg} Now, please provide Document Date (YYYY-MM-DD):",
            next_action="date"
        )

    # Document date step
    if action == "date":
        document_date = data.get("document_date")
        if not document_date:
            return jsonify(reply="Please provide a valid document date.", next_action="date")
        flow_data["document_date"] = document_date
        summary = f"Date: {flow_data.get('document_date')} Now, please provide Item Description:"

        return jsonify(reply=summary, next_action="itm_description")


    # Item description step
    if action == "itm_description":
        itm_description = data.get("itm_description")
        if not itm_description:
            return jsonify(reply="Please provide a valid item description.", next_action="itm_description")

        # --- Fetch item details from HANA DB ---
        item_details = get_item_details_from_db(itm_description)
        if item_details:
            flow_data["ItemCode"] = item_details["ItemCode"]
            flow_data["ItemName"] = item_details["ItemName"]
            flow_data["PriceUnit"] = item_details["PriceUnit"]
            item_msg = f"Got it! Item recorded: {item_details['ItemName']} (Code: {item_details['ItemCode']}, UnitPrice: {item_details['PriceUnit']})"
        else:
            item_msg = f"Item '{itm_description}' not found in database."

        print(user_data)
        return jsonify(
            reply=f"{item_msg}. Now, please enter Item Quantity:",
            next_action="quantity"
        )


    # Quantity step
    if action == "quantity":
        quantity = data.get("quantity")
        if not quantity:
            return jsonify(reply="Please provide a valid Item Quantity.", next_action="quantity")
        flow_data["quantity"] = quantity
        summary = f"quantity: {flow_data.get('quantity')} \nType 'view' to see all details:"

        return jsonify(reply=summary, next_action="confirm")

    if action == "confirm":
        summary = (
            f"✅ Sales Order Summary:\n"
            f"Vendor: {flow_data.get('vendor_name')} (Code: {flow_data.get('vendor_code')})\n"
            f"Document Date: {flow_data.get('document_date')}\n"
            f"Item: {flow_data.get('ItemName')} (Code: {flow_data.get('ItemCode')}, Unit Price: {flow_data.get('PriceUnit')})\n"
            f"Quantity: {flow_data.get('quantity')}"
        )
        return jsonify(reply=summary, next_action="end")

    return jsonify(reply="Invalid step in Sales Order flow.", next_action="start")





def invoice_flow(action, data):
    flow_data = user_data["invoice"]

    if action == "start":
        return jsonify(
            reply="Great! Let's create a Invoice. Please provide the invoice number:",
            next_action="invoice_number"
        )

    # Invoice number step
    if action == "invoice_number":
        invoice_number = data.get("invoice_number")
        if not invoice_number:
            return jsonify(reply="Please provide a valid invoice number.", next_action="invoice_number")

        flow_data["invoice_number"] = invoice_number

        print(user_data)
        return jsonify(
            reply=f"Invoice Number: {invoice_number} Now, please provide Document Date (YYYY-MM-DD):",
            next_action="date"
        )

    # Document date step
    if action == "date":
        document_date = data.get("document_date")
        if not document_date:
            return jsonify(reply="Please provide a valid document date.", next_action="date")
        flow_data["document_date"] = document_date
        summary = f"Date: {flow_data.get('document_date')} Type 'view' to see all details:"

        return jsonify(reply=summary, next_action="confirm")


    if action == "confirm":
        summary = (
            f"✅ Invoice Summary:\n"
            f"Invoice Number: {flow_data.get('invoice_number')}\n"
            f"Document Date: {flow_data.get('document_date')}\n"
        )
        return jsonify(reply=summary, next_action="end")

    return jsonify(reply="Invalid step in Invoice flow.", next_action="start")




@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.json
    action = data.get("action")
    use_case = data.get("use_case")  # sales_order / invoice / other

    # Set use_case if not already set
    if use_case:
        user_data["use_case"] = use_case

    # SALES ORDER FLOW
    if user_data["use_case"] == "sales_order":
        return sales_order_flow(action, data)
    
    # INVOICE FLOW
    elif user_data["use_case"] == "invoice":
        return invoice_flow(action, data)

    # OTHER FLOW
    elif user_data["use_case"] == "other":
        return jsonify(reply="Thank you! No further action implemented yet.", next_action="end")

    return jsonify(reply="Something went wrong. Please start again.", next_action="start")



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
