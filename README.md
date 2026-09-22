# SnacksIT WhatsApp Bulk Sender 🚀

A powerful, user-friendly Streamlit web application designed to help you send bulk WhatsApp template messages using Twilio. It also integrates with Cloudinary to easily upload and attach media to your campaigns.

## 🌟 Key Features

* **Cloudinary Integration**: Drag and drop images to upload them to Cloudinary. Generates a public URL instantly that you can use in your WhatsApp media templates.
* **Bulk Messaging via Twilio**: Upload an Excel sheet of contacts and send approved Twilio Content Templates to hundreds of users at once.
* **Dynamic Variable Mapping**: Automatically fetches your Twilio template and allows you to map template variables (e.g., `{{1}}`) to specific columns in your Excel sheet, custom text, or your uploaded Cloudinary URL.
* **Live Dashboard & Analytics**: Tracks your total contacts, successful messages, and failed deliveries in real-time. 

## 🔄 App Flow & Usage

1. **Upload Media (Optional)**: If your WhatsApp template requires an image, upload it in the "Create Public Image Link" panel. The app uploads it to Cloudinary and copies the public URL to your session.
2. **Upload Contacts**: In the "Send WhatsApp Messages" panel, upload your `.xlsx` Excel file containing your contact list. 
    * *Note: Your Excel file must have a column for the WhatsApp numbers (e.g., `whatsapp_number`).*
3. **Fetch Twilio Template**: Enter your Twilio Content SID (starts with `HX...`). The app will fetch the approved template directly from Twilio and display a preview.
4. **Map Variables**: If your template has placeholders (like `{{1}}`), map them to:
    * A specific column in your Excel file (e.g., `first_name`).
    * Custom text.
    * The Cloudinary URL you generated in step 1.
5. **Send Campaign**: Click the "Send WhatsApp Template" button. The app will process the list and provide a detailed success and error breakdown for each contact.

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.8+
* A Twilio account with a WhatsApp sender number and an approved Content Template.
* A Cloudinary account for media hosting.

### 2. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Rename the `.env.example` file to `.env` and fill in your actual credentials:
```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890

CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

### 4. Run the Application
Start the Streamlit dashboard:
```bash
streamlit run app.py
```

Start the webhook API in a second terminal so incoming WhatsApp replies can be stored in the Inbox:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 5. Connect Twilio Webhooks
Point your Twilio WhatsApp sender or sandbox to the public HTTPS URL of the FastAPI service.

Incoming message webhook:
```text
https://your-domain/webhook/whatsapp
```

Status callback webhook:
```text
https://your-domain/webhook/whatsapp/status
```

### 6. Inbox Requirements
The Inbox needs all of the following:

* `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`
* `database_schema.sql` executed in Supabase
* `api.py` running and reachable from Twilio over HTTPS
* Twilio webhook URLs configured to point at that API

* DEPLOY Api.py on Render (Free) 