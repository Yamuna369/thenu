from flask import Flask, request, jsonify
import uuid
import threading
import time
from datetime import datetime, timedelta
from state_mul import fssai_multiple_filing

app = Flask(__name__)

# Dictionary for managing session IDs and OTP submission statuses
session_data = {}  # Stores session_id -> login_id (or None if not yet available)
otp_data = {}  # Stores session_id -> OTPs

# This will hold current session id and whether OTP is submitted or not
current_session_id = None
otp_submitted = False
otp_submission_status = {}


# @app.route('/', methods=['GET'])
# def index():
#     return jsonify({"message": "System is running"}), 200

# Configuration
SESSION_TIMEOUT = 600  # 10 minutes in seconds
CLEANUP_INTERVAL = 5  # 5 seconds

def cleanup_inactive_sessions():
    """Periodically clean up inactive sessions."""
    while True:
        current_time = datetime.now()
        sessions_to_remove = []
        
        for session_id, data in session_data.items():
            last_active = data.get('last_active')
            if last_active and (current_time - last_active).total_seconds() > SESSION_TIMEOUT:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            delete_session(session_id)
            print(f"Automatically cleaned up inactive session: {session_id}")
        
        time.sleep(CLEANUP_INTERVAL)

def update_session_activity(session_id):
    """Update the last active timestamp for a session."""
    if session_id in session_data:
        session_data[session_id]['last_active'] = datetime.now()

def delete_session(session_id):
    """Deletes session and all associated data instantly."""
    try:
        session_data.pop(session_id, None)
        otp_data.pop(session_id, None)
        otp_submission_status.pop(session_id, None)
        print(f"Session {session_id} deleted successfully.")
        return True
    except Exception as e:
        print(f"Error deleting session {session_id}: {str(e)}")
        return False

@app.route('/delete_session', methods=['POST'])
def handle_delete_session():
    """API endpoint for manually deleting a session, can be called from Selenium or external sources."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400

        # First check if session exists
        if session_id not in session_data:
            return jsonify({"message": "Session not found or already deleted", "session_id": session_id}), 404

        # Try to delete the session
        success = delete_session(session_id)
        
        if success:
            return jsonify({
                "message": "Session deleted successfully",
                "session_id": session_id,
                "status": "deleted"
            }), 200
        else:
            return jsonify({
                "error": "Failed to delete session",
                "session_id": session_id
            }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fssai_state_license', methods=['POST'])
def start_state_task():
    
    global current_session_id
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        client_info = data
        # type =client_info.get("result", {}).get("payload", {}).get("type", [""])[0].strip().lower()

        # if not type:
        #     return jsonify({"error": "Missing 'type' in request data"}), 400

        current_session_id = str(uuid.uuid4())
        current_time  = datetime.now()
        session_data[current_session_id] ={
            "created_at": current_time,
            "last_active": current_time,
            "otp_self": None,
            "otp_authorized": None,
            "verification_code": None,
            "registered_mobileno_otp": None,
            "status": "waiting" 
        }
    
        fssai_instance = fssai_multiple_filing(otp_data, session_data, otp_submission_status, session_id=current_session_id)
        thread = threading.Thread(target=fssai_instance.multiple_service_automation, args=(client_info,))
        
        thread.start()            

        return jsonify({
            "message": "FSSAI state license process started successfully",
            "session_id": current_session_id,
            "status": "waiting_for_otp"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# @app.route('/submit_otps_state', methods=['POST'])
# def submit_state_otps():
#     global current_session_id, otp_submitted
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({"error": "NO JSON DATA RECEIVED"}), 400
#         session_id = data.get("session_id")
#         update_session_activity(session_id)
#         # Get all possible OTPs
#         otp_self = data.get("otp_self")
#         otp_authorized = data.get("otp_authorized")
#         verification_code = data.get("verification_code")
#         registered_mobileno_otp = data.get("registered_mobileno_otp")
#         if session_id not in session_data:
#             return jsonify({"error": "NO ACTIVE SESSION"}), 400
#         if session_id in otp_submission_status and otp_submission_status[session_id] == "pending":
#             # Instead of returning error, wait for processing to complete
#             # This will make the endpoint "blocking" until the OTP is processed
#             timeout = 30  # Set a reasonable timeout (in seconds)
#             start_time = time.time()
            
#             while time.time() - start_time < timeout:
#                 if otp_submission_status[session_id] != "pending":
#                     break
#                 time.sleep(0.5)  # Small delay to avoid CPU spinning
            
#             # After timeout or status change, check the result
#             if otp_submission_status[session_id] == "pending":
#                 return jsonify({"status": "TIMEOUT", "message": "OTP processing took too long"}), 408
            
#             # Return the actual result based on validation status
#             if otp_submission_status[session_id] == "VALID":
#                 login_id = otp_submission_status.get(f"{session_id}_login_id", None)
#                 response = {
#                     "status": "VALID" if not login_id else "Completed",
#                     "session_id": session_id
#                 }
#                 if login_id:
#                     response["Application_no"] = login_id
#                 return jsonify(response), 200
            
#             elif otp_submission_status[session_id] == "INVALID":
#                 otp_submission_status[session_id] = "NEW"
#                 return jsonify({"status": "INVALID", "session_id": session_id}), 400
#         if session_id in otp_submission_status and otp_submission_status[session_id] == "INVALID":
#             print(f"Allowing new OTP submission after INVALID attempt for session {session_id}")
#             otp_submission_status[session_id] = "pending"
#             otp_data[session_id] = {}
#         if session_id not in otp_data:
#             otp_data[session_id] = {}
#         # Handle different OTP stages
#         if otp_self and otp_authorized:
#             # First stage - self and authorized OTPs
#             otp_data[session_id] = {
#                 "otp_self": otp_self,
#                 "otp_authorized": otp_authorized
#             }
#         elif verification_code:
#             # Second stage - verification code
#             otp_data[session_id].update({
#                 "verification_code": verification_code
#             })
#         elif registered_mobileno_otp:
#             # Third stage - registered mobile OTP
#             otp_data[session_id].update({
#                 "registered_mobileno_otp": registered_mobileno_otp
#             })
#         else:
#             return jsonify({"error": "MISSING OTPs"}), 400
        
#         otp_submission_status[session_id] = "pending"
#         print(f"Updated OTPs for session {session_id}: {otp_data[session_id]}")
        
#         # NEW CODE: Wait for Selenium to process the OTP instead of returning immediately
#         timeout = 30  # Set a reasonable timeout (in seconds)
#         start_time = time.time()
        
#         while time.time() - start_time < timeout:
#             if otp_submission_status[session_id] != "pending":
#                 break
#             time.sleep(0.5)  # Small delay to avoid CPU spinning
        
#         # After timeout or status change, check the result
#         if otp_submission_status[session_id] == "pending":
#             return jsonify({"status": "PROCESSING", "message": "OTP still being processed"}), 202
        
#         # Return the actual result based on validation status
#         if otp_submission_status[session_id] == "VALID":
#             login_id = otp_submission_status.get(f"{session_id}_login_id", None)
#             response = {
#                 "status": "VALID" if not login_id else "Completed",
#                 "session_id": session_id
#             }
#             if login_id:
#                 response["Application_no"] = login_id
#             return jsonify(response), 200
        
#         elif otp_submission_status[session_id] == "INVALID":
#             otp_submission_status[session_id] = "NEW"
#             return jsonify({"status": "INVALID", "session_id": session_id}), 400
        
#         # Fallback response if something unexpected happened
#         return jsonify({"status": "PROCESSING", "session_id": session_id}), 202
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

@app.route('/submit_otps_state', methods=['POST'])
def submit_state_otps():
    global current_session_id, otp_submitted
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "NO JSON DATA RECEIVED"}), 400

        session_id = data.get("session_id")
        update_session_activity(session_id)

        # Get all possible OTPs
        otp_self = data.get("otp_self")
        otp_authorized = data.get("otp_authorized")
        verification_code = data.get("verification_code")
        registered_mobileno_otp = data.get("registered_mobileno_otp")

        if session_id not in session_data:
            return jsonify({"error": "NO ACTIVE SESSION"}), 400

        if session_id in otp_submission_status and otp_submission_status[session_id] == "pending":
            return jsonify({"error": "OTP already submitted and being processed"}), 400

        if session_id in otp_submission_status and otp_submission_status[session_id] == "INVALID":
            print(f"Allowing new OTP submission after INVALID attempt for session {session_id}")
            otp_submission_status[session_id] = "pending"
            otp_data[session_id] = {}

        if session_id not in otp_data:
            otp_data[session_id] = {}

        # Handle different OTP stages
        if otp_self and otp_authorized:
            # First stage - self and authorized OTPs
            otp_data[session_id] = {
                "otp_self": otp_self,
                "otp_authorized": otp_authorized
            }
        elif verification_code:
            # Second stage - verification code
            otp_data[session_id].update({
                "verification_code": verification_code
            })
        elif registered_mobileno_otp:
            # Third stage - registered mobile OTP
            otp_data[session_id].update({
                "registered_mobileno_otp": registered_mobileno_otp
            })
        else:
            return jsonify({"error": "MISSING OTPs"}), 400
        
        otp_submission_status[session_id] = "pending"
        print(f"Updated OTPs for session {session_id}: {otp_data[session_id]}")

        return jsonify({"status": "processing", "session_id": session_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check_otps_state', methods=['POST'])
def check_state_otps():
    global otp_submission_status, current_session_id
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"error": "No active session"}), 400
        
        update_session_activity(session_id)

        # First, check if the process has completed successfully
        login_id = otp_submission_status.get(f"{session_id}_login_id", None)
        if login_id:
            return jsonify({
                "status": "Completed",
                "session_id": session_id,
                "Application_no": login_id
            }), 200

        # Check if the session exists but OTP is not submitted yet
        if session_id in session_data and session_id not in otp_submission_status:
            return jsonify({"status": "PENDING", "session_id": session_id}), 202
        
        otp_entry = otp_data.get(session_id, {})
        otp_valid = otp_submission_status.get(session_id)

        if not otp_valid:
            return jsonify({"status": "PROCESSING", "session_id": session_id}), 202

        if otp_valid == "INVALID":
            otp_submission_status[session_id] = "NEW"
            print(f"Returning INVALID for session {session_id}")
            return jsonify({"status": "INVALID", "session_id": session_id}), 400

        if "otp_self" in otp_entry and "otp_authorized" in otp_entry:
            if otp_valid == "pending":
                return jsonify({"status": "PROCESSING", "session_id": session_id}), 202
            elif otp_valid == "VALID":
                return jsonify({"status": "VALID", "session_id": session_id}), 200
            elif otp_valid == "INVALID":
                otp_submission_status[session_id] = "NEW"
                return jsonify({"status": "INVALID", "session_id": session_id}), 400

        if "verification_code" in otp_entry:
            if otp_valid == "pending":
                return jsonify({"status": "PROCESSING", "session_id": session_id}), 202
            elif otp_valid == "VALID":
                    return jsonify({
                        "status": "VALID",
                        "session_id": session_id
                    }), 200
            elif otp_valid == "INVALID":
                otp_submission_status[session_id] = "NEW"
                return jsonify({"status": "INVALID", "session_id": session_id}), 400
            
        if "registered_mobileno_otp" in otp_entry:
            if otp_valid == "pending":
                return jsonify({"status": "PROCESSING", "session_id": session_id}), 202
            elif otp_valid == "VALID":
                    return jsonify({
                        "status": "VALID" if not login_id else "Completed" ,
                        "session_id": session_id,
                        "Application_no": login_id if login_id else "Unknown"
                    }), 200
            elif otp_valid == "INVALID":
                otp_submission_status[session_id] = "NEW"
                return jsonify({"status": "INVALID", "session_id": session_id}), 400
            
        return jsonify({"status": "FAILED", "message": "NO ACTIVE SESSION"}), 400

    except Exception as e:
        print(f"Error in check_otps: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
        # #Immediately return "INVALID" if OTP is incorrect
        # if otp_submission_status.get(session_id) == "INVALID":
        #     print(f"Returning INVALID for session {session_id} without waiting.")
        #     return jsonify({"status": "INVALID", "session_id": session_id}), 400

        # # Check OTP status in a loop
        # for _ in range(10):  # Check for 50 seconds (10 * 5 seconds)
        #     otp_entry = otp_data.get(session_id)
        #     otp_valid = otp_submission_status.get(session_id, "INVALID")

        #     if otp_entry:                
        #         if otp_valid == "pending":
        #             return jsonify({"status": "PROCESSING", "session_id": session_id}), 202
        #         elif otp_valid == "VALID":
        #             # Check if this is the last stage (registered_mobileno_otp)
        #             if "registered_mobileno_otp" in otp_entry:
        #                 return jsonify({
        #                     "status": "VALID" if not login_id else "Completed",
        #                     "session_id": session_id,
        #                     "Application_no": login_id if login_id else "Unknown"
        #                 }), 200
        #             else:
        #                 # For other stages, just return VALID
        #                 return jsonify({"status": "VALID", "session_id": session_id}), 200
        #         elif otp_valid == "INVALID":
        #             if session_id in otp_data:
        #                 del otp_data[session_id]  # Remove old OTP
        #                 break
        #             return jsonify({"status": "INVALID", "session_id": session_id}), 400

        # return jsonify({"status": "FAILED", "message": "NO ACTIVE SESSION"}), 408

@app.route('/get_session', methods=['GET'])
def get_active_sessions():
    """Returns active sessions with their status and duration."""
    current_time = datetime.now()
    active_sessions = {}
    
    for session_id, data in session_data.items():
        duration = (current_time - data['created_at']).total_seconds()
        last_active = (current_time - data['last_active']).total_seconds()
        
        active_sessions[session_id] = {
            "status": data['status'],
            "duration_seconds": int(duration),
            "last_active_seconds_ago": int(last_active),
            "created_at": data['created_at'].isoformat(),
            "last_active": data['last_active'].isoformat()
        }
    
    return jsonify({
        "total_active_sessions": len(active_sessions),
        "active_sessions": active_sessions
    }), 200
           
if __name__ == '__main__':
    # Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
    cleanup_thread.start()
    # Start the Flask application
    app.run(host="0.0.0.0",port=5000)