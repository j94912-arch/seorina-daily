import os,json
from pywebpush import webpush
from pathlib import Path
s=os.getenv('PUSH_SUBSCRIPTIONS'); key=os.getenv('VAPID_PRIVATE_KEY'); mail=os.getenv('VAPID_EMAIL')
if s and key and mail:
 d=json.loads(Path('docs/data.json').read_text()); failed=False
 for sub in json.loads(s):
  try: webpush(subscription_info=sub,data=json.dumps({'title':'SEORINA DAILY','body':'今日蒐集結束，新增 '+str(sum(d['counts'].values()))+' 則；請查看各來源狀態。'},ensure_ascii=False),vapid_private_key=key,vapid_claims={'sub':'mailto:'+mail})
  except Exception as e: print(type(e).__name__); failed=True
 if failed: raise SystemExit(1)
