import base64
import json
import os
import streamlit as st
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Streamlit page configuration
st.set_page_config(page_title="Email Engagement Health Check", layout="wide")

# Gmail API scope for read-only access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# Gemini API endpoint and key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Load from .env

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"Token refresh failed: {e}")
                creds = None
        if not creds:
            if not os.path.exists('credentials.json'):
                st.error("Missing credentials.json. Download it from Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                return None
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_promotional_threads(service, user_id='me', max_threads=5):
    """Fetch up to five email threads labeled as Promotions."""
    try:
        results = service.users().threads().list(userId=user_id, labelIds=['CATEGORY_PROMOTIONS'], maxResults=max_threads).execute()
        threads = results.get('threads', [])
        
        if not threads:
            st.warning("No promotional threads found.")
            return []
        
        thread_data = []
        for thread in threads:
            thread_id = thread['id']
            st.write(f"Fetching thread ID: {thread_id}")
            thread = service.users().threads().get(userId=user_id, id=thread_id).execute()
            messages = thread.get('messages', [])
            
            email_data = []
            for message in messages:
                headers = message['payload']['headers']
                email_info = {
                    'from': '',
                    'to': '',
                    'subject': '',
                    'body': '',
                    'timestamp': ''
                }
                for header in headers:
                    if header['name'].lower() == 'from':
                        email_info['from'] = header['value']
                    if header['name'].lower() == 'to':
                        email_info['to'] = header['value']
                    if header['name'].lower() == 'subject':
                        email_info['subject'] = header['value']
                    if header['name'].lower() == 'date':
                        email_info['timestamp'] = header['value']
                
                try:
                    if 'parts' in message['payload']:
                        for part in message['payload']['parts']:
                            if part['mimeType'] == 'text/plain':
                                body_data = part['body'].get('data', '')
                                if body_data:
                                    email_info['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                                    break
                    else:
                        body_data = message['payload']['body'].get('data', '')
                        if body_data:
                            email_info['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                except Exception as e:
                    st.error(f"Error decoding body for thread {thread_id}: {e}")
                    email_info['body'] = 'Unable to decode message body.'
                
                email_data.append(email_info)
            
            thread_data.append({'thread_id': thread_id, 'emails': email_data})
        
        return thread_data
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        if error.resp.status == 403:
            st.error("Access denied. Ensure mrhappy6600@gmail.com is a test user.")
        elif error.resp.status == 400:
            st.error("Invalid request. Check labelIds and API configuration.")
        return []

def prepare_gemini_payload(email_thread):
    """Prepare payload for Gemini API from email thread."""
    combined_text = "\n".join([f"From: {email['from']}\nSubject: {email['subject']}\nBody: {email['body']}\n" for email in email_thread])
    
    prompt = f"""Analyze the following email thread and provide a JSON object with:
    - engagement_score: 'High' (3+ replies), 'Medium' (1-2 replies), or 'Low' (0 replies)
    - sentiment: 'Positive', 'Neutral', or 'Negative' based on the tone
    - risk_alerts: List of issues like 'Customer sounds unhappy' or 'Multiple follow-ups ignored'
    Thread:
    {combined_text}
    Return only the JSON object."""
    
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

def call_gemini_api(payload):
    """Send email thread data to Gemini API for classification."""
    if not GEMINI_API_KEY:
        st.error("Gemini API key not found. Set GEMINI_API_KEY in .env file.")
        return {
            "engagement_score": "Unknown",
            "sentiment": "Unknown",
            "risk_alerts": ["API key missing"]
        }
    
    headers = {
        "Content-Type": "application/json"
    }
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        generated_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        if generated_text.startswith("```json\n") and generated_text.endswith("\n```"):
            generated_text = generated_text[8:-4]
        return json.loads(generated_text)
    except requests.RequestException as e:
        st.error(f"Gemini API call failed: {e}")
        if hasattr(e, 'response') and e.response:
            st.error(f"Status Code: {e.response.status_code}")
            st.error(f"Error Details: {e.response.text}")
        return {
            "engagement_score": "Unknown",
            "sentiment": "Unknown",
            "risk_alerts": ["API call failed"]
        }
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse Gemini response as JSON: {e}")
        return {
            "engagement_score": "Unknown",
            "sentiment": "Unknown",
            "risk_alerts": ["Invalid response format"]
        }

def main():
    st.title("Email Engagement Health Check")
    st.write("Analyze up to 5 promotional email threads from Gmail using Gemini AI.")
    
    if st.button("Analyze Promotional Emails"):
        with st.spinner("Fetching and analyzing emails..."):
            service = authenticate_gmail()
            if service is None:
                return
            
            threads = get_promotional_threads(service, max_threads=5)
            
            if not threads:
                return
            
            for thread in threads:
                thread_id = thread['thread_id']
                email_thread = thread['emails']
                
                st.subheader(f"Thread ID: {thread_id}")
                
                # Create a DataFrame for display
                email_data = []
                for email in email_thread:
                    email_data.append({
                        "From": email['from'],
                        "To": email['to'],
                        "Subject": email['subject'],
                        "Timestamp": email['timestamp'],
                        "Body": email['body'][:100] + "..." if len(email['body']) > 100 else email['body']
                    })
                
                st.write("**Email Details:**")
                st.dataframe(pd.DataFrame(email_data))
                
                # Analyze with Gemini
                payload = prepare_gemini_payload(email_thread)
                gemini_result = call_gemini_api(payload)
                
                st.write("**Gemini AI Analysis:**")
                analysis_data = [
                    {"Metric": "Engagement Score", "Value": gemini_result.get("engagement_score", "Unknown")},
                    {"Metric": "Sentiment", "Value": gemini_result.get("sentiment", "Unknown")},
                    {"Metric": "Risk Alerts", "Value": ", ".join(gemini_result.get("risk_alerts", [])) or "None"}
                ]
                st.dataframe(pd.DataFrame(analysis_data))
                
                st.markdown("---")

if __name__ == "__main__":
    main()