import os
import sys
import httpx

REQUIRED_ENV_VARS = [
    "SANNEX_API_KEY",
    "PAYSTACK_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "META_WHATSAPP_TOKEN",
    "SLACK_WEBHOOK_URL"
]

def check_env_vars():
    print("\n🔍 Checking Environment Variables...")
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        print(f"❌ Missing required keys: {', '.join(missing)}")
        return False
    print("✅ All required environment variables are set.")
    return True

def check_sannex_connection():
    print("\n🔍 Testing Sannex API Key Connection...")
    api_key = os.getenv("SANNEX_API_KEY", "")
    try:
        res = httpx.post(
            "https://api.sannex.ng/v1/events",
            json={"batch": [{"channel": "healthcheck", "customer_id": "test", "event": "ping"}]},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5.0
        )
        if res.status_code == 202:
            print("✅ Sannex API Key is valid and active.")
            return True
        else:
            print(f"❌ Sannex Auth Failed: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"❌ Could not reach Sannex servers: {e}")
        return False

def main():
    print("=" * 50)
    print("🛠️  SANNEX AGENT STARTER KIT: SYSTEM DOCTOR")
    print("=" * 50)

    env_ok = check_env_vars()
    sannex_ok = check_sannex_connection() if env_ok else False

    print("\n" + "=" * 50)
    if env_ok and sannex_ok:
        print("🎉 ALL CHECKS PASSED: Your environment is production-ready!")
        sys.exit(0)
    else:
        print("⚠️  SYSTEM HEALTH ISSUES DETECTED. Review errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()