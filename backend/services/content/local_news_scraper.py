import logging
import requests
import xml.etree.ElementTree as ET
from typing import List
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

def fetch_local_news() -> List[str]:
    """
    Fetches local Hindi news feed for the Jalaun district regions (Orai, Kalpi, Konch, Jalaun)
    using the Google News RSS search endpoint.
    """
    query = "Jalaun OR Orai OR Kalpi OR Konch"
    url = f"https://news.google.com/rss/search?q={query}&hl=hi&gl=IN&ceid=IN:hi"
    
    headlines = []
    try:
        res = requests.get(url, timeout=3.0, verify=get_ssl_verify())
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            # Find all items and extract titles
            for item in root.findall(".//item")[:8]:  # Get top 8 headlines
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    # Strip source suffix if present (e.g., " - Live Hindustan")
                    title = title_elem.text
                    if " - " in title:
                        title = title.rsplit(" - ", 1)[0]
                    headlines.append(title.strip())
        else:
            logger.warning(f"Google News RSS returned status code {res.status_code}")
    except Exception as e:
        logger.error(f"Error fetching local news: {e}")
        
    # Return default regional headlines if none found or request failed (3 static fallback headlines)
    if not headlines:
        headlines = [
            "Orai Mandi me gehun aur chana ke daam me tezi dekhi gayi.",
            "Jalaun kshetra me kisan samiti ne beej vitran kendra ka shubharambh kiya.",
            "Bundelkhand me naye mausam ki pehli baarish se kisano ke chehre khile."
        ]
    return headlines
