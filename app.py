from flask import Flask, request, jsonify, url_for, send_from_directory
from firebase_admin import credentials, firestore, initialize_app
from flask_cors import CORS
import replicate
import os
from werkzeug.utils import secure_filename
import requests
import stripe
import jwt
import base64
import json
import time

# Decode Firebase credentials
firebase_creds_base64 = os.getenv('FIREBASE_CREDENTIALS')
firebase_creds_json = base64.b64decode(firebase_creds_base64).decode('utf-8')
firebase_creds = json.loads(firebase_creds_json)

# Initialize Firebase app
cred = credentials.Certificate(firebase_creds)
initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# gets the stripe secret key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')
endpoint_secret = os.getenv("STRIPE_ENDPOINT_SECRET")

# Ensure the uploads directory exists
uploads_dir = os.path.join('static', 'uploads')
os.makedirs(uploads_dir, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload():
    print("Upload route hit")  # Confirm route hit
    clerk_user_id = request.headers.get('Clerk-User-Id')
    if not clerk_user_id:
        print("Clerk-User-Id header missing")
        return jsonify({'error': 'Clerk-User-Id header missing'}), 400

    user_ref = db.collection('users').document(clerk_user_id)
    user_doc = user_ref.get()

    if not user_doc.exists:
        print("User not found")
        return jsonify({'error': 'User not found'}), 404

    # Check if an image file is provided
    image_file = request.files.get('image')
    if not image_file:
        print("No image provided")
        return jsonify({'error': 'No image provided'}), 400

    user_data = user_doc.to_dict()
    if user_data.get('credits', 0) <= 0:
        print("Insufficient credits")
        return jsonify({'error': 'Insufficient credits'}), 403

    # Create a user-specific directory if it doesn't exist
    user_uploads_dir = os.path.join(uploads_dir, clerk_user_id)
    os.makedirs(user_uploads_dir, exist_ok=True)

    # Save the uploaded image with a unique filename
    filename = secure_filename(f"{clerk_user_id}_{int(time.time())}_{image_file.filename}")
    filepath = os.path.join(user_uploads_dir, filename)
    image_file.save(filepath)
    print(f"File saved to {filepath}")

    processed_filepath = process_image(filepath)
    if not processed_filepath:
        print("Image processing failed")
        return jsonify({'error': 'Image processing failed'}), 500

    # Deduct credits after successful processing
    new_credits = user_data['credits'] - 1
    user_ref.update({"credits": new_credits})
    print(f"Credits updated for user {clerk_user_id}: {new_credits}")

    original_url = url_for('download_file', filename=f'{clerk_user_id}/{filename}', _external=True)
    processed_url = url_for('download_file', filename=f'{clerk_user_id}/{os.path.basename(processed_filepath)}', _external=True)
    print(f"Original URL: {original_url}")
    print(f"Processed URL: {processed_url}")

    return jsonify({
        'original_image_url': original_url,
        'processed_image_url': processed_url
    }), 200

def process_image(filepath):
    try:
        with open(filepath, "rb") as file:
            output = replicate.run(
                "tencentarc/gfpgan:0fbacf7afc6c144e5be9767cff80f25aff23e52b0708f17e20f9879b2f21516c",
                input={"img": file}
            )
            print(f"Replicate output: {output}")  # Debug output to show replicate output
            if isinstance(output, str) and output.startswith("http"):
                processed_image_path = save_processed_image(output, filepath)
            elif isinstance(output, list) and len(output) > 0 and output[0].startswith("http"):
                processed_image_path = save_processed_image(output[0], filepath)
            else:
                print("Invalid image_data received:", output)
                return None
            return processed_image_path
    except Exception as e:
        print("Error processing image:", str(e))
        return None

def save_processed_image(image_url, original_filepath):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            user_dir = os.path.dirname(original_filepath)
            processed_image_path = os.path.join(user_dir, 'processed_' + os.path.basename(original_filepath))
            with open(processed_image_path, 'wb') as f:
                f.write(response.content)
            return processed_image_path
        else:
            print("Failed to download processed image.")
            return None
    except Exception as e:
        print("Error saving processed image:", str(e))
        return None

@app.route('/api/user-credits', methods=['GET'])
def get_user_credits():
    clerk_user_id = request.headers.get('Clerk-User-Id')
    print(f"Received request for user credits, Clerk-User-Id: {clerk_user_id}")
    
    if not clerk_user_id:
        print("Clerk-User-Id header missing")
        return jsonify({'error': 'Clerk-User-Id header missing'}), 400

    user_ref = db.collection('users').document(clerk_user_id)
    user_doc = user_ref.get()

    if not user_doc.exists:
        # Create new user with 5 initial credits if not exists
        print("User not found, creating new user with 5 credits")
        user_ref.set({'credits': 5})
        return jsonify({'credits': 5}), 200

    user_data = user_doc.to_dict()
    credits = user_data.get('credits', 0)
    print(f"Returning credits for user {clerk_user_id}: {credits}")
    return jsonify({'credits': credits}), 200

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        if '/' not in filename:
            raise ValueError("Invalid filename format")
        user_id, file_name = filename.split('/', 1)
        user_dir = os.path.join(uploads_dir, user_id)
        return send_from_directory(user_dir, file_name, as_attachment=True)
    except ValueError as ve:
        print(f"ValueError: {ve}")
        return jsonify({'error': str(ve)}), 400
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 40404


########################################################################################################

# clerk

CLERK_PEM_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwr6Uwp+8ZXyKXYvp45y5
oFZbn5NbHDszz/pFsjcyS0bOLzadQpme7p6kvzZwaNwnuaimiVa2dlw353jpMAAU
+8dt1M0xE5KNxk0e707F+RSVeBF9F9AsCh/zuaUjfzM6ij7UnVoq0Wstf4xzZEIY
XwmgEKFm+77SL4mKUWBUNtmHNNh0Eyq7wBh3rm77QORvJ0MvOQ4viTjX0twzbiiM
f5O6LkysWOUbdp06WxZNIabfkd2hk+Dgco5z1PftenDmyDdn2fFYvxfTUOMPAhPK
pcHiR6stboJpKq1/I0VfIG7+6LMvN9q8ACOcQ4zdeOmyxcD4Or6HIjtRIubceJIH
YQIDAQAB
-----END PUBLIC KEY-----
"""

def verify_clerk_jwt(token):
    try:
        payload = jwt.decode(token, CLERK_PEM_PUBLIC_KEY, algorithms=['RS256'], audience="your_audience")
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.route('/clerk/webhook', methods=['POST'])
def clerk_webhook():
    token = request.headers.get('Authorization')
    if not token or not verify_clerk_jwt(token):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()

    if data['type'] == 'user.created':
        user_id = data['data']['id']
        print(f"New user created with ID: {user_id}")

        # Check if the user document already exists
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        # If the user document does not exist, create it with 5 initial credits
        if not user_doc.exists:
            user_ref.set({'credits': 5})
        else:
            try:
                user_ref.set({'credits': 5})
                print(f"User {user_id} initialized with 5 credits")
            except Exception as e:
                print(f"Error creating user document for {user_id}: {e}")

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
