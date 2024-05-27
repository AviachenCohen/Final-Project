import os
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import pytz

app = Flask(__name__)

# Set up MongoDB connection
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['logistics_DB']
parcels_collection = db['Parcels']
statuses_collection = db['Statuses']
audits_collection = db['Audits']


@app.route('/')
def home():
    return "Hello, Flask is running!"


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


@app.route('/get_parcels', methods=['GET'])
def get_parcels():
    try:
        print("get_parcels endpoint called")
        parcels = list(parcels_collection.find({}))
        for parcel in parcels:
            parcel['_id'] = str(parcel['_id'])  # Convert ObjectId to string
        return jsonify(parcels)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

