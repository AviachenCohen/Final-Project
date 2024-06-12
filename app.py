import os

from dotenv import load_dotenv
from bson import ObjectId
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import pytz
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)

# Set up MongoDB connection
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['logistics_DB']
parcels_collection = db['Parcels']
statuses_collection = db['Statuses']
audits_collection = db['Audits']
exelot_codes_collection = db['Exelot Codes']

# Load secret key from environment variable
app.config['JWT_SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')

jwt = JWTManager(app)


@app.route('/')
def home():
    return "Hello, Flask is running!"


@app.route('/get_parcels', methods=['GET'])
@jwt_required()
def get_parcels():
    current_user = get_jwt_identity()
    print(f"Current user: {current_user}")

    user_email = current_user['email']
    user_roles = current_user['roles']

    if not user_email:
        raise ValueError("User email not found in token")

    query = {}

    all_access_roles = ['Exelot VP', 'Admin', 'Exelot Workers']
    distributor_roles = ['YDM', 'Cheetah', 'Kexpress', 'Done', 'HFD', 'Buzzr']

    if not any(role in all_access_roles for role in user_roles):  # If user does not have a role with full access
        distributor_role = next((role for role in user_roles if role in distributor_roles), None)
        if distributor_role:
            query['Distributor'] = distributor_role  # Filter by distributor role

    try:
        print("get_parcels endpoint called")     # Fetch parcels based on current_user identity if needed
        parcels = list(parcels_collection.find(query))
        for parcel in parcels:
            parcel['_id'] = str(parcel['_id'])  # Convert ObjectId to string
        return jsonify(parcels)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/update_parcel/<parcel_id>', methods=['PATCH'])
def update_parcel(parcel_id):
    data = request.get_json()
    print("Received data:", data)

    # Validate input
    if 'Status' not in data or not isinstance(data['Status'], str):
        return jsonify({"error": "Status is required and must be a string"}), 400
    if 'Comments' in data and not isinstance(data['Comments'], str):
        return jsonify({"error": "Comments, if provided, must be a string"}), 400

    # Fetch the parcel to get the current distributor and old status
    parcel = parcels_collection.find_one({"ID": parcel_id})
    if not parcel:
        return jsonify({"error": "Parcel not found"}), 404

    distributor = parcel["Distributor"]
    print("Distributor:", distributor)

    # Validate the status for the given distributor
    valid_status = statuses_collection.find_one({"Distributor": distributor, "Status": data["Status"]})
    print("Valid status found:", valid_status)
    if not valid_status:
        return jsonify({"error": "Invalid status for the given distributor"}), 400

    # Get the old Exelot Code and the new Exelot Code
    old_exelot_code = parcel.get("Exelot Code", "")
    new_exelot_code = valid_status["Exelot Code"]

    # Update the parcel with the new status, comments, and Exelot Code
    update_fields = {
        "Status": data["Status"],
        "Comments": data.get("Comments", ""),
        "Exelot Code": new_exelot_code,
        "Status DT": datetime.now(pytz.utc)
    }
    result = parcels_collection.update_one(
        {"ID": parcel_id},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Parcel not found"}), 404

    # Create an audit record
    audit_record = {
        "Parcel ID": parcel_id,
        "Old Status": parcel["Status"],
        "New Status": data["Status"],
        "Old Exelot Code": old_exelot_code,
        "New Exelot Code": new_exelot_code,
        "Change DT": datetime.now(pytz.utc)  # Current UTC date and time
    }
    audits_collection.insert_one(audit_record)

    return jsonify({"message": "Parcel updated successfully"}), 200


@app.route('/get_valid_statuses/<distributor>', methods=['GET'])
def get_valid_statuses(distributor):
    try:
        statuses = statuses_collection.find({"Distributor": distributor})
        valid_statuses = [status["Status"] for status in statuses]
        return jsonify(valid_statuses), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_statuses', methods=['GET'])
def get_statuses():
    statuses = list(statuses_collection.find())
    for status in statuses:
        status['_id'] = str(status['_id'])
    return jsonify(statuses), 200


@app.route('/add_status', methods=['POST'])
def add_status():
    data = request.get_json()
    result = statuses_collection.insert_one(data)
    return jsonify({'inserted_id': str(result.inserted_id)}), 201


@app.route('/update_status/<status_id>', methods=['PATCH'])
def update_status(status_id):
    data = request.get_json()
    result = statuses_collection.update_one({'_id': ObjectId(status_id)}, {'$set': data})
    if result.matched_count == 0:
        return jsonify({'error': 'Status not found'}), 404
    return jsonify({'message': 'Status updated successfully'}), 200


@app.route('/delete_status/<status_id>', methods=['DELETE'])
def delete_status(status_id):
    result = statuses_collection.delete_one({'_id': ObjectId(status_id)})
    if result.deleted_count == 0:
        return jsonify({'error': 'Status not found'}), 404
    return jsonify({'message': 'Status deleted successfully'}), 200


@app.route('/get_parcel_history/<parcel_id>', methods=['GET'])
def get_parcel_history(parcel_id):
    try:
        history = list(audits_collection.find({"Parcel ID": parcel_id}))
        for record in history:
            record['_id'] = str(record['_id'])
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_parcels_by_status_and_distributor', methods=['GET'])
def get_parcels_by_status_and_distributor():
    start_date_str = request.args.get('startDate')
    end_date_str = request.args.get('endDate')
    distributors = request.args.getlist('distributors')  # Get the list of distributors

    try:
        # Parse the ISO string dates to datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Query MongoDB with the date range
    query = {
        "Status DT": {"$gte": start_date, "$lte": end_date},
    }
    if distributors and 'all' not in distributors:
        query["Distributor"] = {"$in": distributors}  # Filter by distributors if provided
    parcels = list(parcels_collection.find(query))

    # Fetch all Exelot Codes
    exelot_codes = {code['Exelot Code']: code['Description'] for code in exelot_codes_collection.find()}

    # Process the parcels to count by status and distributor
    report = {}
    for parcel in parcels:
        status = parcel.get('Status', 'Unknown')
        distributor = parcel.get('Distributor', 'Unknown')
        exelot_code = parcel.get('Exelot Code', 'Unknown')
        exelot_description = exelot_codes.get(exelot_code, 'No description')

        key = (status, distributor, exelot_description)
        if key in report:
            report[key] += 1
        else:
            report[key] = 1

    # Format the report as a list of dictionaries
    report_data = [
        {"Status": k[0], "Distributor": k[1], "ExelotCodeDescription": k[2], "Count": v}
        for k, v in report.items()
    ]

    return jsonify(report_data)


# Generate a token for testing purposes
@app.route('/generate_token', methods=['POST'])
def generate_token():
    email = request.json.get('email')
    roles = request.json.get('roles')
    if not email or not roles:
        return jsonify({"msg": "Missing email or roles"}), 400

    token = create_access_token(identity={"email": email, "roles": roles})
    return jsonify(access_token=token)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
