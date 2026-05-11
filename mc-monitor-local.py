#!/usr/bin/env python3
"""
MC Slot Monitor — Local Version
Runs on YOUR computer (Mac/Windows/Linux desktop), not on a headless server.

Requires:
  pip install playwright requests
  playwright install chromium

Usage:
  python mc-monitor-local.py
"""

import json
import time
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, expect

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "exam_type": "A",  # Motorcycle license
    "test_type": "körprov",  # Driving test (not theory)
    "locations": ["Mjölby", "Linköping", "Örebro", "Norrköping", "Jönköping"],
    "date_window": {
        "start": "2026-06-15",
        "end": "2026-07-31"
    },
    "telegram": {
        "bot_token": "",  # Fill in or use env var TELEGRAM_BOT_TOKEN
        "chat_id": "-5067205563"  # Mc tider group
    },
    "poll_interval_minutes": 5,
    "headless": False,  # Show browser so you can log in manually
}

# ============================================================================
# STATE
# ============================================================================

STATE_FILE = Path(__file__).parent / "monitor-state.json"

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "last_check": None,
        "last_match": None,
        "alert_history": [],
        "session_valid": False,
        "total_checks": 0,
        "errors_in_a_row": 0,
    }

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

# ============================================================================
# TELEGRAM NOTIFICATIONS
# ============================================================================

def send_telegram(message):
    token = CONFIG["telegram"]["bot_token"] or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = CONFIG["telegram"]["chat_id"]
    
    if not token:
        print("⚠️  No Telegram bot token configured. Set TELEGRAM_BOT_TOKEN env var.")
        print(f"   Message would be: {message}")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=30)
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# ============================================================================
# SLOT CHECKING
# ============================================================================

def is_match(location_name, date_str):
    """Check if a slot matches our criteria."""
    # Check location
    loc_index = None
    for i, loc in enumerate(CONFIG["locations"]):
        if loc.lower() in location_name.lower():
            loc_index = i
            break
    
    if loc_index is None:
        return None
    
    # Check date
    try:
        slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start = datetime.strptime(CONFIG["date_window"]["start"], "%Y-%m-%d").date()
        end = datetime.strptime(CONFIG["date_window"]["end"], "%Y-%m-%d").date()
        
        if not (start <= slot_date <= end):
            return None
    except ValueError:
        return None
    
    return {
        "location": CONFIG["locations"][loc_index],
        "priority_rank": loc_index + 1,
        "priority_total": len(CONFIG["locations"]),
        "date": date_str,
    }

def is_duplicate(match, history):
    """Check if we already alerted for this slot recently."""
    key = f"{match['date']}_{match['location']}"
    now = time.time()
    one_hour = 3600
    
    for alert in history:
        if alert["key"] == key and (now - alert["timestamp"]) < one_hour:
            return True
    return False

def record_alert(match, state):
    key = f"{match['date']}_{match['location']}"
    state["alert_history"].append({"key": key, "timestamp": time.time()})
    # Keep last 50
    state["alert_history"] = state["alert_history"][-50:]

# ============================================================================
# BROWSER AUTOMATION
# ============================================================================

def wait_for_login(page, timeout_seconds=300):
    """Wait for user to log in manually."""
    print("\n" + "="*60)
    print("🔐  LOGGA IN MED BANKID")
    print("="*60)
    print("1. Klicka på 'Logga in med BankID' i webbläsaren")
    print("2. Öppna BankID-appen och godkänn")
    print("3. Vänta tills du är inloggad på sidan")
    print(f"4. Scriptet fortsätter automatiskt (timeout: {timeout_seconds}s)")
    print("="*60 + "\n")
    
    start = time.time()
    check_interval = 3
    
    while time.time() - start < timeout_seconds:
        # Check if login button is gone or user name appears
        try:
            # Look for common indicators of being logged in
            # Option 1: "Logga ut" button exists
            logout_btn = page.locator("text=Logga ut").first
            if logout_btn.is_visible(timeout=1000):
                print("✅ Inloggning detekterad!")
                return True
            
            # Option 2: User name or profile element
            profile = page.locator("[class*='user'], [class*='profile'], [class*='inloggad']").first
            if profile.is_visible(timeout=1000):
                print("✅ Inloggning detekterad!")
                return True
                
        except:
            pass
        
        time.sleep(check_interval)
        elapsed = int(time.time() - start)
        if elapsed % 30 == 0:
            print(f"   Väntar... ({elapsed}s)")
    
    print("⏱️  Timeout — ingen inloggning detekterad")
    return False

def find_and_click(page, selectors, description="element"):
    """Try multiple selectors to find and click an element."""
    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=2000):
                elem.click()
                print(f"   Klickade: {description}")
                time.sleep(1)
                return True
        except:
            continue
    print(f"   ⚠️  Hittade inte: {description}")
    return False

def search_for_slots(page):
    """Search for available A-körprov slots."""
    slots = []
    
    try:
        # Navigate to booking section
        # This depends on the exact UI — we'll use flexible selectors
        
        print("\n🔍 Söker efter A körprov...")
        
        # Try to find "Boka prov" or similar
        find_and_click(page, [
            "text=Boka prov",
            "text=Boka körprov",
            "text=Boka",
            "[aria-label*='boka' i]",
        ], "Boka knapp")
        
        # Select license type "A"
        find_and_click(page, [
            "text=A",
            "text=Motorcykel",
            "[value='A']",
            "[aria-label*='motorcykel' i]",
        ], "A-körkort")
        
        # Select test type "körprov"
        find_and_click(page, [
            "text=Körprov",
            "text=Körning",
            "[value='körprov']",
        ], "Körprov")
        
        # For each location, try to search
        for location in CONFIG["locations"]:
            print(f"\n   Söker: {location}")
            
            # Try to enter location
            try:
                # Look for location input or dropdown
                loc_input = page.locator("input[placeholder*='ort' i], input[placeholder*='plats' i], [aria-label*='ort' i]").first
                if loc_input.is_visible(timeout=2000):
                    loc_input.fill(location)
                    time.sleep(0.5)
                    loc_input.press("Enter")
                    time.sleep(1)
            except:
                pass
            
            # Look for date inputs
            try:
                date_from = page.locator("input[type='date']").nth(0)
                date_to = page.locator("input[type='date']").nth(1)
                if date_from.is_visible(timeout=2000):
                    date_from.fill(CONFIG["date_window"]["start"])
                    date_to.fill(CONFIG["date_window"]["end"])
                    time.sleep(0.5)
            except:
                pass
            
            # Click search
            find_and_click(page, [
                "text=Sök",
                "text=Hitta tider",
                "text=Sök tider",
                "[type='submit']",
            ], "Sök")
            
            time.sleep(3)  # Wait for results
            
            # Extract results — look for date/time entries
            try:
                # This is highly dependent on the actual page structure
                # Common patterns for booking systems:
                result_rows = page.locator("tr, .result, .slot, .occasion, [class*='tid']").all()
                
                for row in result_rows:
                    text = row.inner_text()
                    # Try to extract date and location from text
                    # This is a heuristic — needs adjustment for actual page
                    if any(loc.lower() in text.lower() for loc in CONFIG["locations"]):
                        # Try to find date pattern
                        import re
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                        time_match = re.search(r'(\d{2}:\d{2})', text)
                        
                        if date_match:
                            match = is_match(location, date_match.group(1))
                            if match:
                                match["time"] = time_match.group(1) if time_match else ""
                                match["raw_text"] = text[:100]
                                slots.append(match)
                                
            except Exception as e:
                print(f"   Fel vid läsning av resultat: {e}")
        
    except Exception as e:
        print(f"Fel vid sökning: {e}")
    
    return slots

# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    state = load_state()
    
    print("\n" + "="*60)
    print("🛵  MC Slot Monitor — Lokal version")
    print("="*60)
    print(f"Orter: {', '.join(CONFIG['locations'])}")
    print(f"Datum: {CONFIG['date_window']['start']} → {CONFIG['date_window']['end']}")
    print(f"Intervall: var {CONFIG['poll_interval_minutes']}e minut")
    print("="*60 + "\n")
    
    # Check Telegram config
    if not CONFIG["telegram"]["bot_token"] and not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("⚠️  VARNING: Ingen Telegram bot token konfigurerad!")
        print("   Sätt TELEGRAM_BOT_TOKEN miljövariabel eller uppdatera CONFIG.")
        print("   Notiser kommer bara skrivas ut i terminalen.\n")
    
    with sync_playwright() as p:
        # Use persistent context so session is saved between runs
        user_data_dir = Path(__file__).parent / "browser-data"
        user_data_dir.mkdir(exist_ok=True)
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=CONFIG["headless"],
            args=["--disable-blink-features=AutomationControlled"] if not CONFIG["headless"] else [],
        )
        
        page = browser.new_page()
        
        # Navigate to booking page
        print("🌐 Öppnar Trafikverkets bokningssida...")
        page.goto("https://fp.trafikverket.se/Boka/ng/")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Check if already logged in
        print("🔍 Kollar inloggningsstatus...")
        try:
            logout_btn = page.locator("text=Logga ut").first
            if logout_btn.is_visible(timeout=3000):
                print("✅ Redan inloggad!")
                state["session_valid"] = True
            else:
                print("🔐 Inte inloggad — väntar på BankID")
                logged_in = wait_for_login(page)
                state["session_valid"] = logged_in
                if not logged_in:
                    print("❌ Inloggning misslyckades — avslutar")
                    browser.close()
                    return
        except:
            print("🔐 Inte inloggad — väntar på BankID")
            logged_in = wait_for_login(page)
            state["session_valid"] = logged_in
            if not logged_in:
                print("❌ Inloggning misslyckades — avslutar")
                browser.close()
                return
        
        save_state(state)
        
        # Main monitoring loop
        print("\n" + "="*60)
        print("✅ Övervakning startad!")
        print("="*60)
        print("Tryck Ctrl+C för att avsluta\n")
        
        try:
            while True:
                state["total_checks"] += 1
                state["last_check"] = datetime.now().isoformat()
                
                print(f"\n🔍 Check #{state['total_checks']} — {datetime.now().strftime('%H:%M:%S')}")
                
                # Refresh page to get fresh data
                page.reload()
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                
                # Check still logged in
                try:
                    logout_btn = page.locator("text=Logga ut").first
                    if not logout_btn.is_visible(timeout=3000):
                        print("⚠️  Utloggad — väntar på ny inloggning")
                        logged_in = wait_for_login(page, timeout_seconds=120)
                        if not logged_in:
                            print("❌ Inloggning misslyckades — pausar")
                            state["errors_in_a_row"] += 1
                            if state["errors_in_a_row"] >= 3:
                                print("❌ För många fel — avslutar")
                                break
                            time.sleep(60)
                            continue
                        state["errors_in_a_row"] = 0
                except:
                    pass
                
                # Search for slots
                slots = search_for_slots(page)
                
                if slots:
                    print(f"\n   📋 Hittade {len(slots)} potentiella tider")
                    for slot in slots:
                        print(f"      {slot['date']} {slot.get('time', '')} — {slot['location']} (prio {slot['priority_rank']})")
                        
                        if not is_duplicate(slot, state["alert_history"]):
                            message = (
                                f"🚨 <b>Ledig MC-tid hittad!</b>\n"
                                f"📅 {slot['date']}\n"
                                f"🕐 {slot.get('time', 'Tid ej specificerad')}\n"
                                f"📍 {slot['location']}\n"
                                f"📊 Prioritet: {slot['priority_rank']}/{slot['priority_total']}\n"
                                f"🔗 <a href='https://fp.trafikverket.se/Boka/ng/'>Boka nu</a>"
                            )
                            
                            print(f"   🔔 SKICKAR ALERT!")
                            send_telegram(message)
                            record_alert(slot, state)
                            state["last_match"] = datetime.now().isoformat()
                        else:
                            print(f"      (redan notifierad)")
                else:
                    print("   Inga matchande tider hittade")
                
                state["errors_in_a_row"] = 0
                save_state(state)
                
                # Wait before next check
                wait_seconds = CONFIG["poll_interval_minutes"] * 60
                print(f"\n   ⏳ Nästa check om {CONFIG['poll_interval_minutes']} minuter...")
                time.sleep(wait_seconds)
                
        except KeyboardInterrupt:
            print("\n\n👋 Avslutar...")
        finally:
            save_state(state)
            browser.close()
            print("✅ Browser stängd")

if __name__ == "__main__":
    main()
