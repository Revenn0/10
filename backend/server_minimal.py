from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import imaplib
import email
from email.header import decode_header
import re
import os
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory storage for alerts (no database)
alerts_cache: List[Dict] = []
gmail_credentials = {
    "email": os.environ.get('GMAIL_EMAIL', ''),
    "password": os.environ.get('GMAIL_APP_PASSWORD', '')
}

app = FastAPI(title="Bike Tracker - Gmail IMAP Only")

# CORS
DEFAULT_ALLOWED_ORIGINS = [
    "https://tracker-dashboard-2.preview.emergentagent.com",
    "https://tracker4th.netlify.app",
    "http://localhost:3000"
]
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    try:
        extra = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        DEFAULT_ALLOWED_ORIGINS.extend(extra)
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(DEFAULT_ALLOWED_ORIGINS)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALERT_CATEGORIES = [
    "Crash Detected",
    "Heavy Impact",
    "Light Sensor",
    "Out Of Country",
    "No Communication",
    "Over-turn",
    "Tamper Alert",
    "Low Battery",
    "Motion",
    "New Positions",
    "High Risk Area",
    "Custom GeoFence",
    "Rotation Stop",
    "Temperature",
    "Pressure",
    "Humidity",
    "Other"
]


class GmailConfigRequest(BaseModel):
    email: str
    app_password: str


class SyncRequest(BaseModel):
    limit: int = 100


def connect_imap(email_addr: str, app_password: str):
    """Connect to Gmail via IMAP"""
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(email_addr, app_password)
        return imap
    except Exception as e:
        logger.error(f"IMAP connection error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to Gmail: {str(e)}")


def get_email_body(msg):
    """Extract email body"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except Exception:
            pass
    return body


def parse_tracker_email(body: str) -> dict:
    """Parse tracker email to extract important information"""
    data = {
        "alert_type": "",
        "time": "",
        "location": "",
        "latitude": "",
        "longitude": "",
        "device_serial": "",
        "tracker_name": "",
        "account_name": ""
    }
    
    try:
        alert_type_match = re.search(r'Alert type:\s*(.+)', body)
        if alert_type_match:
            data["alert_type"] = alert_type_match.group(1).strip()
        
        time_match = re.search(r'Time:\s*(.+?)(?:\(|$)', body)
        if time_match:
            data["time"] = time_match.group(1).strip()
        
        location_match = re.search(r'Location:\s*(.+)', body)
        if location_match:
            data["location"] = location_match.group(1).strip()
        
        coords_match = re.search(r'Latitude, Longitude:\s*([-\d.]+),\s*([-\d.]+)', body)
        if coords_match:
            data["latitude"] = coords_match.group(1).strip()
            data["longitude"] = coords_match.group(2).strip()
        
        device_match = re.search(r'Device Serial Number:\s*(.+)', body)
        if device_match:
            data["device_serial"] = device_match.group(1).strip()
        
        tracker_match = re.search(r'Tracker Name:\s*(.+)', body)
        if tracker_match:
            data["tracker_name"] = tracker_match.group(1).strip()
        
        account_match = re.search(r'Account name:\s*(.+)', body)
        if account_match:
            data["account_name"] = account_match.group(1).strip()
    except Exception as e:
        logger.error(f"Error parsing email: {str(e)}")
    
    return data


def categorize_alert(alert_type: str) -> str:
    """Categorize alert based on type"""
    alert_lower = alert_type.lower()
    
    if "heavy impact" in alert_lower:
        return "Heavy Impact"
    elif "light sensor" in alert_lower:
        return "Light Sensor"
    elif "out of country" in alert_lower:
        return "Out Of Country"
    elif "no communication" in alert_lower:
        return "No Communication"
    elif "over-turn" in alert_lower or "overturn" in alert_lower:
        return "Over-turn"
    elif "tamper" in alert_lower:
        return "Tamper Alert"
    elif "low battery" in alert_lower:
        return "Low Battery"
    elif "motion" in alert_lower:
        return "Motion"
    elif "new position" in alert_lower:
        return "New Positions"
    elif "high risk" in alert_lower:
        return "High Risk Area"
    elif "geofence" in alert_lower:
        return "Custom GeoFence"
    elif "rotation" in alert_lower:
        return "Rotation Stop"
    elif "temperature" in alert_lower:
        return "Temperature"
    elif "pressure" in alert_lower:
        return "Pressure"
    elif "humidity" in alert_lower:
        return "Humidity"
    else:
        return "Other"


@app.get("/")
def read_root():
    return {"message": "Bike Tracker API - Gmail IMAP Only", "status": "running"}


@app.post("/api/gmail/configure")
async def configure_gmail(request: GmailConfigRequest):
    """Configure Gmail credentials (stored in memory)"""
    global gmail_credentials
    
    # Test connection
    try:
        imap = connect_imap(request.email, request.app_password)
        imap.logout()
    except HTTPException as e:
        raise e
    
    gmail_credentials["email"] = request.email
    gmail_credentials["password"] = request.app_password
    
    logger.info(f"Gmail configured: {request.email}")
    
    return {"success": True, "message": "Gmail configured successfully"}


@app.post("/api/gmail/sync")
async def sync_gmail(sync_req: SyncRequest = None):
    """Sync emails from Gmail and store in memory cache"""
    global alerts_cache
    
    if not gmail_credentials["email"] or not gmail_credentials["password"]:
        raise HTTPException(status_code=400, detail="Gmail not configured. Use /api/gmail/configure first")
    
    limit = sync_req.limit if sync_req else 100
    
    try:
        imap = connect_imap(gmail_credentials["email"], gmail_credentials["password"])
        imap.select("INBOX")
        
        _, message_numbers = imap.search(None, 'FROM "alerts-no-reply@tracking-update.com"')
        email_ids = message_numbers[0].split()
        
        # Get last N emails
        email_ids = email_ids[-limit:]
        
        new_alerts = []
        email_id_set = {alert.get("email_id") for alert in alerts_cache}
        
        for email_id in email_ids:
            email_id_str = email_id.decode()
            
            if email_id_str in email_id_set:
                continue
            
            try:
                _, msg_data = imap.fetch(email_id, "(RFC822)")
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)
                body = get_email_body(msg)
                
                parsed = parse_tracker_email(body)
                category = categorize_alert(parsed["alert_type"])
                
                alert = {
                    "id": len(alerts_cache) + len(new_alerts) + 1,
                    "email_id": email_id_str,
                    "alert_type": category,
                    "alert_time": parsed["time"],
                    "location": parsed["location"],
                    "latitude": parsed["latitude"],
                    "longitude": parsed["longitude"],
                    "device_serial": parsed["device_serial"],
                    "tracker_name": parsed["tracker_name"],
                    "account_name": parsed["account_name"],
                    "created_at": datetime.now().isoformat(),
                    "raw_body": body[:500]
                }
                
                new_alerts.append(alert)
                
            except Exception as e:
                logger.error(f"Error processing email {email_id_str}: {str(e)}")
        
        imap.logout()
        
        # Add new alerts to cache
        alerts_cache.extend(new_alerts)
        
        logger.info(f"Synced {len(new_alerts)} new alerts from Gmail")
        
        return {
            "success": True,
            "message": f"{len(new_alerts)} new alerts synced",
            "new_alerts": len(new_alerts),
            "total_cached": len(alerts_cache)
        }
        
    except Exception as e:
        logger.error(f"Gmail sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/api/alerts/list")
async def list_alerts(
    category: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=10000)
):
    """Get alerts from memory cache (no database)"""
    filtered_alerts = alerts_cache
    
    if category and category != "All":
        filtered_alerts = [a for a in alerts_cache if a.get("alert_type") == category]
    
    # Sort by created_at (newest first)
    filtered_alerts = sorted(filtered_alerts, key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Apply limit
    filtered_alerts = filtered_alerts[:limit]
    
    # Calculate stats
    total_count = len(filtered_alerts)
    
    over_turn_count = sum(1 for a in filtered_alerts if a.get("alert_type") == "Over-turn")
    no_communication_count = sum(1 for a in filtered_alerts if a.get("alert_type") == "No Communication")
    heavy_impact_count = sum(1 for a in filtered_alerts if a.get("alert_type") == "Heavy Impact")
    
    # Category stats
    category_stats = {}
    for cat in ALERT_CATEGORIES:
        category_stats[cat] = sum(1 for a in filtered_alerts if a.get("alert_type") == cat)
    
    return {
        "alerts": filtered_alerts,
        "stats": {
            "total": total_count,
            "overTurn": over_turn_count,
            "noCommunication": no_communication_count,
            "heavyImpactAlerts": heavy_impact_count,
            "categories": category_stats
        },
        "connected": bool(gmail_credentials["email"]),
        "email": gmail_credentials["email"]
    }


@app.get("/api/alerts/categories")
async def get_categories():
    """Get all available alert categories"""
    category_stats = {}
    for cat in ALERT_CATEGORIES:
        category_stats[cat] = sum(1 for a in alerts_cache if a.get("alert_type") == cat)
    
    return {
        "categories": ALERT_CATEGORIES,
        "stats": category_stats
    }


@app.delete("/api/alerts/clear-all")
async def clear_all_alerts():
    """Clear all cached alerts"""
    global alerts_cache
    alerts_cache = []
    return {"success": True, "message": "All alerts cleared from cache"}


@app.get("/api/bikes/list")
async def list_bikes():
    """Get all bikes from cached alerts"""
    # Group alerts by tracker_name
    bikes_dict = {}
    
    for alert in alerts_cache:
        tracker_name = alert.get("tracker_name")
        if not tracker_name:
            continue
        
        if tracker_name not in bikes_dict:
            bikes_dict[tracker_name] = {
                "tracker_name": tracker_name,
                "device_serial": alert.get("device_serial"),
                "latest_alert_at": alert.get("created_at"),
                "alert_count": 0
            }
        
        bikes_dict[tracker_name]["alert_count"] += 1
        
        # Update latest_alert_at if this alert is newer
        if alert.get("created_at") > bikes_dict[tracker_name]["latest_alert_at"]:
            bikes_dict[tracker_name]["latest_alert_at"] = alert.get("created_at")
    
    # Convert to list and sort by latest_alert_at
    bikes = list(bikes_dict.values())
    bikes = sorted(bikes, key=lambda x: x.get("latest_alert_at", ""), reverse=True)
    
    return {"bikes": bikes}


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "gmail_configured": bool(gmail_credentials["email"]),
        "cached_alerts": len(alerts_cache)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
