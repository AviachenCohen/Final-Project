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

    # Validate input
    if 'Status' not in data or not isinstance(data['Status'], str):
        return jsonify({"error": "Status is required and must be a string"}), 400
    if 'Comments' in data and not isinstance(data['Comments'], str):
        return jsonify({"error": "Comments, if provided, must be a string"}), 400

    # Fetch the parcel to get the current distributor and old status
    parcel = parcels_collection.find_one({"ID": parcel_id})
    if not parcel:
        return jsonify({"error": "Parcel not found"}), 404

    current_distributor = parcel["Distributor"]

    # Validate status
    status_doc = statuses_collection.find_one({"Distributor": current_distributor, "Status": data["Status"]})
    if not status_doc:
        return jsonify({"error": "Invalid status for the given distributor"}), 400

    # Prepare fields to update
    update_fields = {
        "Status": data["Status"],
        "Status DT": datetime.now(pytz.utc)
    }
    if "Comments" in data:
        update_fields["Comments"] = data["Comments"]

    # Update the parcel
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
        "Old Exelot Code": parcel["Exelot Code"],
        "New Exelot Code": status_doc["Exelot Code"],
        "Change DT": datetime.now(pytz.utc)
    }
    audits_collection.insert_one(audit_record)

    return jsonify({"message": "Parcel updated successfully"}), 200


if __name__ == '__main__':
    app.run(debug=True)
