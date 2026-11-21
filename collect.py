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
def photos():
 key=os.getenv('SERPAPI_KEY')
 if not key: return '未設定 SERPAPI_KEY'
 cutoff=now-dt.timedelta(days=7)
 urls={x.get('url') for x in data['items'] if x.get('source')=='photo'}
 images={x.get('image') for x in data['items'] if x.get('source')=='photo'}
 added=0; skipped=0
 for q in ('설인아 포토','설인아 사진'):
  r=requests.get('https://serpapi.com/search.json',params={'engine':'google_news','q':q+' when:7d','gl':'kr','hl':'ko','api_key':key},timeout=35)
  if not r.ok: raise ValueError('搜尋 API HTTP '+str(r.status_code))
  j=r.json()
  if j.get('error'): raise ValueError('搜尋 API 回報錯誤')
  rows=j.get('news_results',[])
  for item in rows:
   for e in ([item]+(item.get('stories') or [])):
    url=e.get('link',''); image=e.get('thumbnail',''); title=e.get('title',''); raw=e.get('date','')
    if not all(isinstance(v,str) for v in (url,image,title,raw)) or not url.startswith('https://') or not image.startswith('https://') or '설인아' not in title: skipped+=1; continue
    try:
     date=dt.datetime.strptime(raw,'%m/%d/%Y, %I:%M %p, %z').astimezone(now.tzinfo)
    except ValueError:
     try: date=dt.datetime.fromisoformat(raw.replace('Z','+00:00')); assert date.tzinfo
     except (ValueError,AssertionError): skipped+=1; continue
    if not cutoff<=date<=now: skipped+=1; continue
    u=urlsplit(url); url=u._replace(fragment='',query='&'.join(part for part in u.query.split('&') if part and not part.lower().startswith(('utm_','fbclid=')))).geturl()
    if url in urls or image in images: continue
    urls.add(url); images.add(image)
    source=e.get('source') or {}; publisher=source.get('name','') if isinstance(source,dict) else str(source)
    add('photo',hashlib.sha256(url.encode()).hexdigest(),title,url,date.isoformat(),image=image,publisher=publisher); added+=1
  print('photo results:',len(rows),'added:',added,'skipped:',skipped)
 return f'新增 {added} 則；略過 {skipped} 筆日期或照片未確認資料'
for name,fn in [('news',news),('photo',photos)]:
 try: status[name]=fn() or '蒐集完成'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
