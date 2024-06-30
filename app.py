import base64
import os
from io import StringIO
import csv
from dotenv import load_dotenv
from bson import ObjectId
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_cors import CORS

# from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
CORS(app)

# Set up MongoDB connection
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['logistics_DB']
parcels_collection = db['Parcels']
statuses_collection = db['Statuses']
audits_collection = db['Audits']
exelot_codes_collection = db['Exelot Codes']
distributors_collection = db['Distributors']


# Load secret key from environment variable
# app.config['JWT_SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
# jwt = JWTManager(app)

# # Email configuration
# EMAIL_ADDRESS = 'aviacoheen@gmail.com'
# EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
# SMTP_SERVER = "smtp.gmail.com"
# SMTP_PORT = 587


# Function to send email
def send_email(to_email, subject, body):
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "overdue.system.management@gmail.com"
        app_password = os.getenv('EMAIL_PASSWORD')  # Ensure you have set this in your .env file

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())

        print(f"Email successfully sent to {to_email}")
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")


def check_parcels_and_notify():
    try:
        forty_eight_hours_ago = datetime.now(pytz.utc) - timedelta(hours=48)
        query = {"Status DT": {"$lt": forty_eight_hours_ago}}
        parcels = list(parcels_collection.find(query))
        print(f"Found {len(parcels)} parcels that need updates.")

        if parcels:
            # Use distributor names for querying
            distributor_names = {parcel["Distributor"] for parcel in parcels}
            print(f"Distributor Names: {distributor_names}")

            # Querying with string name
            distributors_cursor = distributors_collection.find({"Name": {"$in": list(distributor_names)}})
            distributors = list(distributors_cursor)
            print(f"Found {len(distributors)} distributors.")

            for distributor in distributors:
                distributor_email = distributor["Email"]
                distributor_name = distributor["Name"]
                subject = "Parcels status update is required"
                body = (f"Dear {distributor_name},"
                        f"\n\nWe have identified parcels whose status has not been updated for over 48 hours:\n")

                for parcel in parcels:
                    if parcel["Distributor"] == distributor["Name"]:
                        body += (f"- Parcel ID: {parcel['ID']}, Status: {parcel['Status']}, "
                                 f"Last Update: {parcel['Status DT']}\n")

                body += ("\nPlease update the status of these parcels as soon as possible, at the link:"
                         "\nhttps://aviachen.wixsite.com/overdue-system-manag"
                         ".\n\nBest regards,"
                         "\nOverdue Management System Team")

                print(f"Sending email to {distributor_email}")
                send_email(distributor_email, subject, body)
        else:
            print("No parcels found that need updates.")
    except Exception as e:
        print(f"Error in check_parcels_and_notify: {e}")


# Set up the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Schedule the check_parcels_and_notify function to run daily at 8 AM Israel time
scheduler.add_job(
    check_parcels_and_notify,
    trigger=CronTrigger(day_of_week='sun,mon,tue,wed,thu', hour=9, minute=0, timezone='Asia/Jerusalem')
)


@app.route('/')
def home():
    return "Hello, Flask is running!"


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


@app.route('/get_parcels_for_parcels_management', methods=['GET'])
def get_parcels_for_parcels_management():
    try:
        print("get_parcels endpoint called")

        # Calculate the datetime for 48 hours ago
        forty_eight_hours_ago = datetime.now(timezone.utc) - timedelta(hours=48)

        # Query to filter parcels
        query = {
            "Status DT": {"$lt": forty_eight_hours_ago},
            "Exelot Code": {"$nin": ["73", "52", "99"]}
        }

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
        statuses = statuses_collection.find({
            "Distributor": distributor,
            "Active": True  # Only fetch active statuses
        })
        valid_statuses = [status["Status"] for status in statuses]
        return jsonify(valid_statuses), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_parcels_with_csv', methods=['POST'])
def update_parcels_with_csv():
    try:
        print('starting to process csv file')
        data = request.get_json()
        print(f'got the data from request: {data}')  # Print the entire data to check its structure
        csv_content_base64 = data.get('csvContent', '')
        if not csv_content_base64:
            raise ValueError("No CSV file data found in the request")

        # Decode the base64 encoded CSV content
        csv_content = base64.b64decode(csv_content_base64).decode('utf-8')
        print(f'Decoded CSV content:\n{csv_content}')  # Print the decoded CSV content to ensure it's correct

        # Ensure csv_content is being read correctly by printing it before parsing
        print(f"CSV Content Length: {len(csv_content)}")
        if len(csv_content) < 50:
            print(f"CSV Content (first 50 chars): {csv_content[:50]}")

        csv_reader = csv.DictReader(StringIO(csv_content))
        print('i have csv reader')

        updated_parcels = 0
        row_count = 0  # Counter to track the number of rows

        for row in csv_reader:
            row_count += 1
            print(f'Processing row {row_count}: {row}')  # Print each row to debug field names and values
            # Ensure row is correctly parsed by printing its type and content
            print(f'Row type: {type(row)}, Row content: {row}')
            parcel_id = row['ID']
            new_status = row['Status']
            new_comments = row['Comments']
            # next row is your addition to be deleted later
            # new_status_dt = row['Status DT']
            print('the fields are:')
            print(parcel_id, new_status, new_comments)

            print(f"Processing parcel with ID: {parcel_id}")

            parcel = parcels_collection.find_one({"ID": parcel_id})
            if not parcel:
                print(f"Parcel with ID {parcel_id} not found.")
                continue

            distributor = parcel["Distributor"]
            valid_status = statuses_collection.find_one({"Distributor": distributor, "Status": new_status})
            if not valid_status:
                print(f"Invalid status {new_status} for distributor {distributor}.")
                continue

            old_exelot_code = parcel.get("Exelot Code", "")
            new_exelot_code = valid_status["Exelot Code"]

            audit_record = {
                "Parcel ID": parcel_id,
                "Old Status": parcel["Status"],
                "New Status": new_status,
                "Old Exelot Code": old_exelot_code,
                "New Exelot Code": new_exelot_code,
                # "Change DT": new_status_dt  # delete this after updating the 3 files
                "Change DT": datetime.now(pytz.utc)
            }
            audits_collection.insert_one(audit_record)

            update_fields = {
                "Status": new_status,
                "Comments": new_comments,
                "Exelot Code": new_exelot_code,
                # "Status DT": new_status_dt   # delete this after updating the 3 files
                "Status DT": datetime.now(pytz.utc)
            }
            parcels_collection.update_one({"ID": parcel_id}, {"$set": update_fields})

            updated_parcels += 1

            print(f"Updated parcel with ID: {parcel_id}")

        print(f"Updated {updated_parcels} parcels.")
        return jsonify({"message": "Parcels updated successfully", "updated_parcels": updated_parcels}), 200
    except Exception as e:
        print(f"Error processing CSV: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/get_statuses', methods=['GET'])
def get_statuses():
    statuses = list(statuses_collection.find({'Active': True}))  # Only fetch active statuses
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


@app.route('/deactivate_status/<status_id>', methods=['PATCH'])
def deactivate_status(status_id):
    try:
        # Set the Active field to false
        result = statuses_collection.update_one(
            {'_id': ObjectId(status_id)},
            {'$set': {'Active': False}}
        )
        if result.matched_count == 0:
            return jsonify({'error': 'Status not found'}), 404
        return jsonify({'message': 'Status deactivated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


@app.route('/get_lost_parcels', methods=['GET'])
def get_lost_parcels():
    start_date_str = request.args.get('startDate')
    end_date_str = request.args.get('endDate')
    distributors = request.args.getlist('distributors')  # Get the list of distributors
    sites = request.args.getlist('sites')  # Get the list of sites
    status = request.args.get('status')  # Status code for lost parcels
    print(
        f"Received start date: {start_date_str}, end date: {end_date_str}, distributors: {distributors},"
        f" sites: {sites}, status: {status}")

    try:
        # Parse the ISO string dates to datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Query MongoDB with the date range
    lost_parcels_query = {
        'Status': status,
        "Status DT": {"$gte": start_date, "$lte": end_date},
    }

    # Build the query filter
    if distributors and 'all' not in distributors:
        lost_parcels_query["Distributor"] = {"$in": distributors}  # Filter by distributors if provided
    if sites and 'all' not in sites:
        lost_parcels_query['Site'] = {'$in': sites}

    print(f"MongoDB query: {lost_parcels_query}")

    parcels = list(parcels_collection.find(lost_parcels_query))
    print(f"Found parcels: {parcels}")

    # Process the parcels to count by status and distributor
    report = {}
    for parcel in parcels:
        distributor = parcel.get('Distributor', 'Unknown')
        site = parcel.get('Site', 'Unknown')

        key = (distributor, site)
        if key in report:
            report[key] += 1
        else:
            report[key] = 1

    # Format the report as a list of dictionaries
    report_data = [
        {"Distributor": k[0], "Site": k[1], "TotalLost": v}
        for k, v in report.items()
    ]
    print(f"Generated report data: {report_data}")

    return jsonify(report_data)


@app.route('/get_parcels_for_held_report', methods=['GET'])
def get_parcels_for_held_report():
    start_date_str = request.args.get('startDate')
    end_date_str = request.args.get('endDate')
    distributors = request.args.getlist('distributors')  # Get the list of distributors
    sites = request.args.getlist('sites')  # Get the list of sites
    exelot_codes = request.args.getlist('exelotCodes')  # Get the list of exelot codes for held parcels
    print(
        f"Received start date: {start_date_str}, end date: {end_date_str}, distributors: {distributors},"
        f" sites: {sites}, exelot codes: {exelot_codes}")

    try:
        # Parse the ISO string dates to datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Query MongoDB with the date range
    parcels_for_held_report_query = {
        "Exelot Code": {"$in": exelot_codes},
        "Status DT": {"$gte": start_date, "$lte": end_date},
    }

    # Build the query filter
    if distributors and 'all' not in distributors:
        parcels_for_held_report_query["Distributor"] = {"$in": distributors}  # Filter by distributors if provided
    if sites and 'all' not in sites:
        parcels_for_held_report_query['Site'] = {'$in': sites}

    print(f"MongoDB query: {parcels_for_held_report_query}")

    parcels = list(parcels_collection.find(parcels_for_held_report_query))
    print(f"Found parcels: {parcels}")

    # Process the parcels to count by site and distributor
    report = {}
    for parcel in parcels:
        distributor = parcel.get('Distributor', 'Unknown')
        site = parcel.get('Site', 'Unknown')

        key = (distributor, site)
        if key in report:
            report[key] += 1
        else:
            report[key] = 1

    # Format the report as a list of dictionaries
    report_data = [
        {"Distributor": k[0], "Site": k[1], "TotalParcels": v}
        for k, v in report.items()
    ]
    print(f"Generated report data: {report_data}")

    return jsonify(report_data)


@app.route('/get_parcels_for_pudo_report', methods=['GET'])
def get_parcels_for_pudo_report():
    start_date_str = request.args.get('startDate')
    end_date_str = request.args.get('endDate')
    distributors = request.args.getlist('distributors')  # Get the list of distributors
    sites = request.args.getlist('sites')  # Get the list of sites
    exelot_codes = request.args.getlist('exelotCodes')  # Get the list of exelot codes for held parcels
    print(
        f"Received start date: {start_date_str}, end date: {end_date_str}, distributors: {distributors},"
        f" sites: {sites}, exelot codes: {exelot_codes}")

    try:
        # Parse the ISO string dates to datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        seven_days_ago = datetime.now(timezone.utc) - timedelta(hours=168)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # Query MongoDB with the date range and the 7-day threshold
    parcels_for_pudo_report_query = {
        "Exelot Code": {"$in": exelot_codes},
        "Status DT": {"$gte": start_date, "$lte": end_date},
    }

    # Build the query filter
    if distributors and 'all' not in distributors:
        parcels_for_pudo_report_query["Distributor"] = {"$in": distributors}  # Filter by distributors if provided
    if sites and 'all' not in sites:
        parcels_for_pudo_report_query['Site'] = {'$in': sites}

    print(f"MongoDB query: {parcels_for_pudo_report_query}")

    try:
        # Query MongoDB
        parcels = list(parcels_collection.find(parcels_for_pudo_report_query))
        print(f"Found parcels: {parcels}")
    except Exception as e:
        print(f"Error querying MongoDB: {e}")
        return jsonify({"error": "Error querying database"}), 500

    try:
        # Filter parcels to exclude those not older than 7 days
        filtered_parcels = [
            parcel for parcel in parcels
            if parcel['Status DT'].replace(tzinfo=timezone.utc) < seven_days_ago
        ]
        print(f"Filtered parcels: {filtered_parcels}")
    except KeyError as e:
        print(f"KeyError during filtering: {e}")
        return jsonify({"error": "Missing 'Status DT' in parcel data"}), 500

    # Process the parcels to count by site and distributor
    report = {}
    for parcel in filtered_parcels:
        distributor = parcel.get('Distributor', 'Unknown')
        site = parcel.get('Site', 'Unknown')

        key = (distributor, site)
        if key in report:
            report[key] += 1
        else:
            report[key] = 1

    # Format the report as a list of dictionaries
    report_data = [
        {"Distributor": k[0], "Site": k[1], "TotalParcels": v}
        for k, v in report.items()
    ]
    print(f"Generated report data: {report_data}")

    return jsonify(report_data)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# @app.route('/get_parcels', methods=['GET'])
# @jwt_required()
# def get_parcels():
#     current_user = get_jwt_identity()
#     print(f"Current user: {current_user}")
#
#     if isinstance(current_user, dict):
#         user_email = current_user.get('sub')    # Ensure we're getting 'sub' claim
#         user_roles = current_user.get('roles', [])
#     else:
#         user_email = current_user.get('email')
#         user_roles = []
#
#     if not user_email:
#         return jsonify({"error": "User email not found in token"}), 422
#
#     query = {}
#
#     all_access_roles = ['Exelot VP', 'Admin', 'Exelot Workers']
#     distributor_roles = ['YDM', 'Cheetah', 'Kexpress', 'Done', 'HFD', 'Buzzr']
#
#     if not any(role in all_access_roles for role in user_roles):  # If user does not have a role with full access
#         distributor_role = next((role for role in user_roles if role in distributor_roles), None)
#         if distributor_role:
#             query['Distributor'] = distributor_role  # Filter by distributor role
#
#     try:
#         print("get_parcels endpoint called")     # Fetch parcels based on current_user identity if needed
#         parcels = list(parcels_collection.find(query))
#         for parcel in parcels:
#             parcel['_id'] = str(parcel['_id'])  # Convert ObjectId to string
#         return jsonify(parcels)
#     except Exception as e:
#         print(f"Error occurred: {str(e)}")
#         return jsonify({"error": str(e)}), 500


# # Generate a token for testing purposes
# @app.route('/generate_token', methods=['POST'])
# def generate_token():
#     sub = request.json.get('sub')
#     roles = request.json.get('roles')
#     if not sub or not roles:
#         return jsonify({"msg": "Missing email or roles"}), 400
#
#     token = create_access_token(identity={"email": sub, "roles": roles})
#     return jsonify(access_token=token)


# @app.route('/update_parcels_with_csv', methods=['POST'])
# def update_parcels_with_csv():
#     if not request.data:
#         return jsonify({'error': 'No file part'}), 400
#
#     try:
#         csv_file = request.data.decode('utf-8')  # Read the CSV content from the request
#         csv_reader = csv.DictReader(csv_file.splitlines())
#         for row in csv_reader:
#             try:
#                 parcel_id, status, comments = row
#                 # Find the relevant parcel
#                 parcel = parcels_collection.find_one({"ID": parcel_id})
#                 if parcel:
#                     distributor = parcel["Distributor"]
#                     valid_status = statuses_collection.find_one({"Distributor": distributor, "Status": status})
#                     if valid_status:
#                         new_exelot_code = valid_status["Exelot Code"]
#                         update_fields = {
#                             "Status": status,
#                             "Comments": comments,
#                             "Exelot Code": new_exelot_code,
#                             "Status DT": datetime.now(pytz.utc)
#                         }
#                         result = parcels_collection.update_one(
#                             {"ID": parcel_id},
#                             {"$set": update_fields}
#                         )
#                         if result.matched_count > 0:
#                             audit_record = {
#                                 "Parcel ID": parcel_id,
#                                 "Old Status": parcel["Status"],
#                                 "New Status": status,
#                                 "Old Exelot Code": parcel.get("Exelot Code", ""),
#                                 "New Exelot Code": new_exelot_code,
#                                 "Change DT": datetime.now(pytz.utc)
#                             }
#                             audits_collection.insert_one(audit_record)
#             except Exception as e:
#                 print(f"Error processing row {row}: {str(e)}")
#                 continue
#         return jsonify({'message': 'CSV processed successfully'}), 200
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
