import os
import json

cookies_json = os.environ.get('TIKTOK_COOKIES', '')
if cookies_json:
    try:
        parsed = json.loads(cookies_json)
        with open('tiktok_cookies.json', 'w') as f:
            json.dump(parsed, f)
        print(f'✅ TikTok cookies loaded ({len(parsed)} cookies)')
    except Exception as e:
        print(f'⚠️ Cookies load failed: {e}')
else:
    print('ℹ️ TIKTOK_COOKIES not set')
