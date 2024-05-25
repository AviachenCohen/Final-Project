import re


# Sites Bills Validations - Not necessarily required
# def validate_site(data):
#     if 'ID' not in data or not isinstance(data['ID'], str):
#         return False, "ID is required and must be a string"
#     if 'Name' not in data or not isinstance(data['Name'], str):
#         return False, "Name is required and must be a string"
#     return True, ""


# Airway Bills Validations - Not necessarily required
# def validate_airway_bill(airway_bill):
#     errors = []
#
#     # ID validation
#     id_pattern = re.compile(r'^\d{3}-\d{8}$')  # Assuming ID format is 3 digits-8 digits
#     if not airway_bill.get('ID'):
#         errors.append("ID is required.")
#     elif not isinstance(airway_bill['ID'], str):
#         errors.append("ID must be a string.")
#     elif len(airway_bill['ID']) == 0:
#         errors.append("ID cannot be an empty string.")
#     elif not id_pattern.match(airway_bill['ID']):
#         errors.append("ID must follow the pattern xxx-xxxxxxxx (e.g., 123-45678901).")
#
#     # From validation
#     if not airway_bill.get('From'):
#         errors.append("From is required.")
#     if not isinstance(airway_bill['From'], str):
#         errors.append("From must be a string.")
#     elif len(airway_bill['From']) == 0:
#         errors.append("From cannot be an empty string.")
#
#     # To validation
#     if airway_bill.get('To') != "Tel Aviv, IL":
#         errors.append("To must be 'Tel Aviv, IL'.")
#     elif not isinstance(airway_bill['To'], str):
#         errors.append("To must be a string.")
#     elif len(airway_bill['To']) == 0:
#         errors.append("To cannot be an empty string.")
#
#     # ETA validation
#     if not airway_bill.get('ETA'):
#         errors.append("ETA is required.")
#     elif not isinstance(airway_bill['ETA'], str):
#         errors.append("ETA must be a valid date.")
#
#     # ATA validation
#     if not airway_bill.get('ATA'):
#         errors.append("ATA is required.")
#     elif not isinstance(airway_bill['ATA'], str):
#         errors.append("ATA must be a valid date.")
#
#     return errors
#
#
# def insert_airway_bill(airway_bill, collection):
#     errors = validate_airway_bill(airway_bill)
#     if errors:
#         return {"success": False, "errors": errors}
#     collection.insert_one(airway_bill)
#     return {"success": True}

#
# # Parcels Validations
# def validate_parcel_status(data, db):
#     if 'Status' not in data or not isinstance(data['Status'], str):
#         return False, "Status is required and must be a string"
#     if not db['Statuses'].find_one({"Status": data['Status']}):
#         return False, "Status must reference a valid Status"
#     if 'Comment' in data and not isinstance(data['Comment'], str):
#         return False, "Comment, if provided, must be a string"
#     return True, ""


