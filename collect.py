import os,json,datetime as dt, requests, feedparser
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs
import base64, hashlib
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
P=Path('docs/data.json'); now=dt.datetime.now(ZoneInfo('Asia/Taipei')); day=now.date()-dt.timedelta(days=1)
start=dt.datetime.combine(day,dt.time.min,now.tzinfo); end=start+dt.timedelta(days=1)
data=json.loads(P.read_text(encoding="utf8")) if P.exists() else {'items':[]}; seen={x['id'] for x in data['items']}; status={}; counts={}
def add(source,id,title,url,date,**extra):
 id=source+':'+str(id)
 if id not in seen:
  seen.add(id); data['items'].append(dict(source=source,id=id,title=title,url=url,date=date,batch=extra.pop("batch",str(now.date())),**extra)); counts[source]=counts.get(source,0)+1

def get(url,**kw):
 r=requests.get(url,timeout=35,**kw); r.raise_for_status(); return r.json()
def news():
 r=requests.get('https://news.google.com/rss/search',params={'q':'설인아 when:7d','hl':'ko','gl':'KR','ceid':'KR:ko'},timeout=35); r.raise_for_status(); f=feedparser.parse(r.content)
 if f.bozo and not f.entries: raise ValueError('RSS parse error')
 for e in f.entries:
  add('news',e.get('id',e.link),e.title,e.link,e.get('published',''))
def parse_date(raw):
 from email.utils import parsedate_to_datetime
 if not isinstance(raw,str): return None
 raw=raw.strip()
 for fmt in ('%m/%d/%Y, %I:%M %p, %z','%m/%d/%Y, %I:%M %p %z','%m/%d/%Y, %H:%M, %z','%m/%d/%Y, %H:%M %z'):
  try: return dt.datetime.strptime(raw,fmt)
  except ValueError: pass
 try:
  d=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
  if d.tzinfo: return d
 except ValueError: pass
 try:
  d=parsedate_to_datetime(raw)
  if d.tzinfo: return d
 except (ValueError,TypeError): pass
 # Relative dates are estimates, not exact publication times.
 m=re.fullmatch(r'(\d+)\s*(minute|hour|day|week)s?\s+ago',raw,re.I)
 if m: return now-dt.timedelta(**{m[2].lower()+'s':int(m[1])})
 m=re.fullmatch(r'(\d+)\s*(분|시간|일|주)\s*전',raw)
 if m: return now-dt.timedelta(**{{'분':'minutes','시간':'hours','일':'days','주':'weeks'}[m[2]]:int(m[1])})
 return None

def canonical(url):
 u=urlsplit(url)
 return u._replace(fragment='',query='&'.join(x for x in u.query.split('&') if x and not x.lower().startswith(('utm_','fbclid=','gclid=')))).geturl()

def walk(rows):
 for e in rows:
  if not isinstance(e,dict): continue
  if e.get('link') or e.get('title') and not e.get('stories'): yield e
  yield from walk(e.get('stories') or [])

def photos():
 from collections import Counter
 key=os.getenv('SERPAPI_KEY')
 if not key: return '未設定 SERPAPI_KEY'
 urls={canonical(x['url']) for x in data['items'] if x.get('source')=='photo' and x.get('url')}
 images={x.get('image') for x in data['items'] if x.get('source')=='photo'}
 skipped=Counter(); added=0; failures=0
 for q in ('설인아 포토','설인아 사진'):
  try:
   r=requests.get('https://serpapi.com/search.json',params={'engine':'google_news','q':q,'gl':'kr','hl':'ko','api_key':key},timeout=35)
   if not r.ok: raise ValueError('HTTP '+str(r.status_code))
   j=r.json()
   if j.get('error'): raise ValueError('API error')
  except Exception as exc:
   failures+=1; print('query failed:',q,type(exc).__name__); continue
  rows=list(walk(j.get('news_results') or []))
  for e in rows:
   url=e.get('link') or ''; image=e.get('thumbnail') or e.get('thumbnail_small') or e.get('image') or ''; image=(image.get('url') or image.get('link') or '') if isinstance(image,dict) else image; title=e.get('title') or ''; raw=e.get('date') or ''
   reason=None; date=parse_date(raw)
   if not isinstance(url,str) or not url.startswith(('https://','http://')): reason='missing_url'
   elif not isinstance(image,str) or not image.startswith(('https://','http://')): reason='missing_image'
   elif not isinstance(title,str) or '설인아' not in title: reason='title_not_matched'
   else:
    url=canonical(url)
    if url in urls or image in images: reason='duplicate'
   if reason:
    skipped[reason]+=1; print('skip:',reason,'date:',repr(raw),'title:',str(title)[:160]); continue
   urls.add(url); images.add(image)
   source=e.get('source') or {}; publisher=source.get('name','') if isinstance(source,dict) else str(source)
   add('photo',hashlib.sha256(url.encode()).hexdigest(),title,url,date.isoformat() if date and date<=now else "",image=image,publisher=publisher,collected_at=now.isoformat()); added+=1
  print('photo query:',q,'results:',len(rows),'added cumulative:',added,'skipped:',dict(skipped))
 return f'新增 {added} 則；略過 {sum(skipped.values())} 筆；查詢失敗 {failures} 次；'+str(dict(skipped))
for name,fn in [('news',news),('photo',photos)]:
 try: status[name]=fn() or '蒐集完成'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
