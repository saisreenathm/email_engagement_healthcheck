import re
from datetime import datetime, timedelta
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import json

# Download NLTK data for sentiment analysis
nltk.download('vader_lexicon')

# Sample email thread data (simulated)
email_thread = [
    {"from": "lead@example.com", "to": "you@company.com", "subject": "Inquiry about Product", "body": "Hi, I'm interested in your product. Can you share pricing details?", "timestamp": "2025-06-01 10:00:00"},
    {"from": "you@company.com", "to": "lead@example.com", "subject": "Re: Inquiry about Product", "body": "Hi, thanks for reaching out! Here's our pricing: Basic - $99/month, Pro - $199/month. Let me know if you'd like a demo.", "timestamp": "2025-06-01 12:00:00"},
    {"from": "lead@example.com", "to": "you@company.com", "subject": "Re: Inquiry about Product", "body": "Thanks for the details. The Pro plan sounds good, but I'm concerned about the setup process.", "timestamp": "2025-06-02 09:00:00"},
    {"from": "you@company.com", "to": "lead@example.com", "subject": "Re: Inquiry about Product", "body": "Great to hear you're interested in the Pro plan! The setup is straightforward, and we offer free onboarding support. Would you like to schedule a call to discuss?", "timestamp": "2025-06-02 11:00:00"},
    {"from": "lead@example.com", "to": "you@company.com", "subject": "Re: Inquiry about Product", "body": "I'm not sure, the price seems high, and I haven't heard back on my last question about integration.", "timestamp": "2025-06-05 14:00:00"}
]

# Initialize sentiment analyzer
sid = SentimentIntensityAnalyzer()

def classify_email_type(subject, body):
    """Classify email type based on subject and body."""
    subject = subject.lower()
    body = body.lower()
    if "inquiry" in subject or "interested" in body:
        return "Inquiry"
    elif "re:" in subject:
        return "Follow-up"
    return "Other"

def calculate_engagement_score(thread):
    """Calculate engagement score based on number of replies and response times."""
    reply_count = len(thread) - 1  # Subtract initial email
    if reply_count >= 3:
        return "High"
    elif reply_count >= 1:
        return "Medium"
    return "Low"

def analyze_sentiment(emails):
    """Analyze sentiment of the email thread."""
    combined_text = " ".join(email["body"] for email in emails)
    scores = sid.polarity_scores(combined_text)
    compound_score = scores["compound"]
    if compound_score >= 0.05:
        return "Positive"
    elif compound_score <= -0.05:
        return "Negative"
    return "Neutral"

def calculate_responsiveness(thread):
    """Calculate average reply time and check for recent responses."""
    reply_times = []
    for i in range(1, len(thread)):
        sent_time = datetime.strptime(thread[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
        reply_time = datetime.strptime(thread[i]["timestamp"], "%Y-%m-%d %H:%M:%S")
        reply_times.append((reply_time - sent_time).total_seconds() / 3600)  # Hours
    avg_reply_time = sum(reply_times) / len(reply_times) if reply_times else float('inf')
    
    last_response = datetime.strptime(thread[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
    days_since_last = (datetime.now() - last_response).days
    
    return {"avg_reply_time_hours": round(avg_reply_time, 2), "days_since_last_response": days_since_last}

def assess_relationship_quality(responsiveness, sentiment, engagement):
    """Assess relationship quality based on responsiveness, sentiment, and engagement."""
    if responsiveness["days_since_last_response"] > 7:
        return "This lead has gone cold"
    elif sentiment == "Negative":
        return "Lead expresses concerns"
    elif engagement == "High" and sentiment == "Positive":
        return "Strong engagement"
    return "Neutral relationship"

def detect_risk_alerts(thread, sentiment, responsiveness):
    """Detect potential risks in the email thread."""
    alerts = []
    if sentiment == "Negative":
        alerts.append("Customer sounds unhappy")
    if responsiveness["days_since_last_response"] > 3 and thread[-1]["from"] == "lead@example.com":
        alerts.append("Multiple follow-ups ignored")
    return alerts

def email_health_check(thread):
    """Perform email engagement health check."""
    analysis = {
        "Type of Email": classify_email_type(thread[0]["subject"], thread[0]["body"]),
        "Engagement Score": calculate_engagement_score(thread),
        "Sentiment": analyze_sentiment(thread),
        "Responsiveness": calculate_responsiveness(thread),
        "Relationship Quality": "",
        "Risk Alerts": []
    }
    analysis["Relationship Quality"] = assess_relationship_quality(analysis["Responsiveness"], analysis["Sentiment"], analysis["Engagement Score"])
    analysis["Risk Alerts"] = detect_risk_alerts(thread, analysis["Sentiment"], analysis["Responsiveness"])
    return analysis

# Run analysis
result = email_health_check(email_thread)

# Output result as JSON
print(json.dumps(result, indent=2))
