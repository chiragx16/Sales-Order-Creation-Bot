from flask import Flask, request, jsonify
from flask_cors import CORS
from hdbcli import dbapi  # SAP HANA client
from dotenv import load_dotenv
from datetime import datetime
from uuid import uuid4
import os

load_dotenv()

db_address = os.getenv("DB_ADDRESS")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


app = Flask(__name__)
CORS(app)

# Temporary storage for user input (for demonstration, resets on server restart)
user_data = {}  # key = session_id, value = {use_case, sales_order, invoice, ...}



# --- HANA Database connection function ---
def get_customer_code_from_db(customer_name):
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

        # cursor.execute("SELECT T0.[CardCode] FROM OCRD T0 WHERE T0.[CardName] = %s", (customer_name,))
        cursor.execute(query, (customer_name,))
        result = cursor.fetchone()
        print("Result : ", result)
        cursor.close()
        conn.close()

        if result:
            return result[0]  # customer_code
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
        WHERE LOWER(T0."ItemName") LIKE LOWER(?) 
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





def sales_order_flow(action, data, session_data):
    flow_data = session_data["sales_order"]

    if "items" not in flow_data:
        flow_data["items"] = []

    # --- Start flow ---
    if action == "start":
        return jsonify(
            reply="Great! Let's create a Sales Order. Please provide the Customer Name:",
            next_action="customer_name"
        )

    # --- Customer name step ---
    if action == "customer_name":
        customer_name = data.get("customer_name")
        if not customer_name:
            return jsonify(reply="Please provide a valid Customer Name.", next_action="customer_name")

        flow_data["customer_name"] = customer_name

        customer_code = get_customer_code_from_db(customer_name)
        if customer_code:
            flow_data["customer_code"] = customer_code
            msg = f"Customer recorded: {customer_name} (Code: {customer_code})."
            return jsonify(
                reply=f"{msg} Now, please provide Document Date (YYYY-MM-DD):",
                next_action="date"
            )
        else:
            # Customer not found → ask again
            return jsonify(
                reply=f"❌ Customer '{customer_name}' not found in database. Please try again with a valid Customer Name:",
                next_action="customer_name"
            )

    # --- Date step ---
    if action == "date":
        document_date = data.get("document_date")
        if not document_date:
            return jsonify(reply="Please provide a valid document date (YYYY-MM-DD).", next_action="date")
        
        # Try to parse multiple date formats and convert to yyyy-mm-dd
        parsed_date = None
        possible_formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y",
            "%Y-%b-%d", "%Y-%B-%d",  # 2020-Jan-16 / 2020-January-16
            "%d-%b-%Y", "%d-%B-%Y",  # 30-Dec-2025 / 30-December-2025
            "%d-%b-%y", "%d-%B-%y",  # 15-Jul-05 / 15-July-05
            "%Y/%b/%d", "%d/%b/%Y", "%d/%B/%Y"
        ]
        for fmt in possible_formats:
            try:
                parsed_date = datetime.strptime(document_date, fmt)
                break
            except ValueError:
                continue

        if not parsed_date:
            return jsonify(
                reply="⚠️ Invalid date format. Please enter the date in YYYY-MM-DD format (e.g., 2025-10-29).",
                next_action="date"
            )

        normalized_date = parsed_date.strftime("%Y-%m-%d")
        flow_data["document_date"] = normalized_date
        return jsonify(
            reply=f"Date recorded as {normalized_date}. Please provide the first Item Description:",
            next_action="itm_description"
        )


    # --- Item description step ---
    if action == "itm_description":
        itm_description = data.get("itm_description")
        if not itm_description:
            return jsonify(reply="Please provide a valid item description.", next_action="itm_description")

        item_details = get_item_details_from_db(itm_description)
        if item_details:
            flow_data["current_item"] = {
                "ItemCode": item_details["ItemCode"],
                "ItemName": item_details["ItemName"],
                "PriceUnit": item_details["PriceUnit"]
            }
            msg = f"Item recorded: {item_details['ItemName']} (Code: {item_details['ItemCode']}, Unit Price: {item_details['PriceUnit']})."
            return jsonify(
                reply=f"{msg} Now, please enter Item Quantity:",
                next_action="quantity"
            )
        else:
            # Item not found → ask again
            return jsonify(
                reply=f"❌ Item '{itm_description}' not found in database. Please enter a valid Item Description:",
                next_action="itm_description"
            )


    # --- Quantity step ---
    if action == "quantity":
        quantity = data.get("quantity")
        if not quantity:
            return jsonify(reply="Please provide a valid quantity.", next_action="quantity")

        if "current_item" not in flow_data:
            return jsonify(reply="No current item found. Please add item description first.", next_action="itm_description")

        flow_data["current_item"]["Quantity"] = quantity
        flow_data["items"].append(flow_data["current_item"])
        del flow_data["current_item"]

        count = len(flow_data["items"])
        return jsonify(
            reply=f"Item #{count} added successfully! Do you want to add another item? (yes/no)",
            next_action="add_more_items"
        )

    # --- Add more items decision ---
    if action == "add_more_items":
        user_response = data.get("add_more_items", "").strip().lower()
        if user_response in ["yes", "y"]:
            return jsonify(
                reply="Okay, please provide the next Item Description:",
                next_action="itm_description"
            )
        elif user_response in ["no", "n"]:
            return jsonify(
                reply="Alright! Preparing Sales Order summary... Type 'view' to show details",
                next_action="preview"
            )
        else:
            return jsonify(reply="Please reply with 'yes' or 'no'.", next_action="add_more_items")
        

    # --- Preview step ---
    if action == "preview":
        customer_name = flow_data.get("customer_name", "")
        customer_code = flow_data.get("customer_code", "")
        document_date = flow_data.get("document_date", "")
        items = flow_data.get("items", [])

        # Prepare fallback text
        summary_lines = [
            f"Customer: {customer_name} (Code: {customer_code})",
            f"Document Date: {document_date}",
            "Items:"
        ]
        for idx, item in enumerate(items, start=1):
            summary_lines.append(
                f"  {idx}. {item['ItemName']} (Code: {item['ItemCode']}, Qty: {item['Quantity']}, UnitPrice: {item['PriceUnit']})"
            )
        summary_text = "✅ Sales Order Preview:\n" + "\n".join(summary_lines)

        # Prepare clean HTML table layout
        html_items = ""
        for i, item in enumerate(items, start=1):
            html_items += f"""
                <tr class='border-b border-gray-200'>
                    <td class='px-4 py-2 text-center text-gray-800 font-medium'>{i}</td>
                    <td class='px-4 py-2 text-gray-700'>{item['ItemName']}</td>
                    <td class='px-4 py-2 text-center text-gray-700'>{item['ItemCode']}</td>
                    <td class='px-4 py-2 text-center text-gray-700'>{item['Quantity']}</td>
                    <td class='px-4 py-2 text-center text-gray-700'>{item['PriceUnit']}</td>
                    <td class='px-4 py-2 text-center'>
                        <button 
                            class='bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm'
                            onclick="deleteItem({i})">
                            Delete
                        </button>
                    </td>
                </tr>
            """



        reply_html = f"""
        <div id='preview-container'>
        <div class='bg-white border border-gray-300 rounded-xl shadow-md p-4 w-full max-w-2xl'>
            <h3 class='text-lg font-bold text-primary mb-3'>✅ Sales Order Preview</h3>
            <div class='text-gray-700 mb-2'><span class='font-semibold'>Customer:</span> {customer_name} ({customer_code})</div>
            <div class='text-gray-700 mb-4'><span class='font-semibold'>Document Date:</span> {document_date}</div>

            <div class='overflow-x-auto'>
                <table class='min-w-full border border-gray-200 text-sm'>
                    <thead class='bg-gray-100 text-gray-800 font-semibold'>
                        <tr>
                            <th class='px-4 py-2 text-left'>#</th>
                            <th class='px-4 py-2 text-left'>Item Name</th>
                            <th class='px-4 py-2 text-left'>Code</th>
                            <th class='px-4 py-2 text-left'>Qty</th>
                            <th class='px-4 py-2 text-left'>Unit Price</th>
                            <th class='px-4 py-2 text-left'>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_items}
                    </tbody>
                </table>
            </div><br>
            <div class='text-gray-700 mb-2'><span>Please type <b>Confirm</b> for SAP posting</span></div>
        </div>
        </div>
        """

        return jsonify({
            "reply": summary_text,   # Fallback
            "reply_html": reply_html, # Rich formatted version
            "next_action": "confirm", # <-- move to final confirm next
            "summary_data": flow_data
        })
    

    # --- Delete item step ---
    if action == "delete_item":
        print("data : ", data)
        print("flow_data : ", flow_data)
        delete_index = data.get("delete_index")
        if delete_index is None:
            return jsonify(reply="Please specify which item number to delete.", next_action="preview")

        try:
            delete_index = int(delete_index)
            if delete_index < 1 or delete_index > len(flow_data.get("items", [])):
                return jsonify(reply=f"⚠️ Invalid item number: {delete_index}.", next_action="preview")

            removed_item = flow_data["items"].pop(delete_index - 1)
            reply_msg = f"🗑️ Deleted item #{delete_index}: {removed_item['ItemName']}."

            if len(flow_data["items"]) == 0:
                return jsonify(
                    reply=f"{reply_msg}\nNo items left. Please add new item description:",
                    next_action="itm_description"
                )

            # Return updated preview
            return sales_order_flow("preview", data, session_data)

        except Exception as e:
            print("Delete item error:", e)
            return jsonify(reply="⚠️ Something went wrong deleting the item.", next_action="preview")



    # --- Confirm step ---
    if action == "confirm":
        # Here you would finalize the order, e.g., save to DB
        # For now, just acknowledge

        user_response = data.get("confirm", "").strip().lower()
        print(user_response)
        if user_response in ["confirm", "yes", "y"]:
            return jsonify(
                reply="✅ Sales Order confirmed and saved successfully!",
                next_action="end"
            )
        else:
            return jsonify(
                reply="Please reply with 'Confirm'",
                next_action="confirm"
            )







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
    session_id = data.get("session_id")  # unique id from frontend
    action = data.get("action")
    use_case = data.get("use_case")  # sales_order / invoice / other

    # Create session if not exist
    if session_id not in user_data:
        user_data[session_id] = {
            "use_case": None,
            "sales_order": {},
            "invoice": {},
            "other": {}
        }

    session_data = user_data[session_id]

    # Update use_case
    if use_case:
        session_data["use_case"] = use_case

    # Route flows per session
    if session_data["use_case"] == "sales_order":
        return sales_order_flow(action, data, session_data)
    elif session_data["use_case"] == "invoice":
        return invoice_flow(action, data, session_data)
    else:
        return jsonify(reply="Something went wrong. Please start again.", next_action="start")



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
