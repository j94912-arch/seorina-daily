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
  seen.add(id); data['items'].append(dict(source=source,id=id,title=title,url=url,date=date,batch=str(now.date()),**extra)); counts[source]=counts.get(source,0)+1

def get(url,**kw):
 r=requests.get(url,timeout=35,**kw); r.raise_for_status(); return r.json()
def news():
 r=requests.get('https://news.google.com/rss/search',params={'q':'설인아 when:7d','hl':'ko','gl':'KR','ceid':'KR:ko'},timeout=35); r.raise_for_status(); f=feedparser.parse(r.content)
 if f.bozo and not f.entries: raise ValueError('RSS parse error')
 for e in f.entries:
  add('news',e.get('id',e.link),e.title,e.link,e.get('published',''))
def canonical(url,source):
 u=urlsplit(url); host=(u.hostname or '').lower(); path=u.path
 if source=='ig' and host in ('instagram.com','www.instagram.com'):
  m=re.fullmatch(r'/(?:p|reel)/([A-Za-z0-9_-]+)/?',path)
  if m: return m[1], 'https://www.instagram.com'+path.rstrip('/')+'/'
 if source=='x' and host in ('x.com','www.x.com','twitter.com','www.twitter.com'):
  m=re.match(r'/[^/]+/status/(\d+)(?:/|$)',path) or re.match(r'/i/web/status/(\d+)(?:/|$)',path)
  if m: return m[1], 'https://x.com/i/web/status/'+m[1]
 return None

def resolve(url, source):
 if not isinstance(url,str): return None
 if c:=canonical(url,source): return c
 u=urlsplit(url)
 if u.hostname not in ('www.google.com','google.com') or u.scheme!='https': return None
 if u.path=='/url':
  q=parse_qs(u.query); return canonical(q.get('q',q.get('url',['']))[0],source)
 if u.path!='/goto': return None
 try:
  r=requests.get(url,allow_redirects=False,timeout=10,stream=True)
  with r:
   return canonical(r.headers.get('Location',''),source)
 except requests.RequestException: return None

def ig_info(item):
 title=str(item.get('title') or ''); snippet=str(item.get('snippet') or '')
 author=bool(re.search(r'(?:photos? by|videos? by|reels? by).*?\(@_seorina\)',title,re.I) or re.search(r'(?:^|[-–]\s*)@?_seorina\s+on\s+',snippet,re.I) or re.search(r'^_seorina\s*·',snippet,re.I))
 if re.search(r'@[\w.]+\s+on\s+',snippet,re.I) and not re.search(r'@_seorina\s+on\s+',snippet,re.I): author=False
 dates=set()
 for s in (title,snippet):
  for m in re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}',s):
   try: dates.add(dt.datetime.strptime(m,'%B %d, %Y').date())
   except ValueError: pass
 relative=str(item.get('date') or '')
 old=bool(re.search(r'\d+\s*(?:個月|年|months?|years?)|(?:[2-9]|\d{2,})\s*(?:週|周|weeks?)',relative,re.I))
 if dates and max(dates)<now.date()-dt.timedelta(days=7): old=True
 return author,old

def social(source,queries):
 key=os.getenv('SERPAPI_KEY')
 if not key: return '未設定 SERPAPI_KEY'
 old={v[0] for item in data['items'] if item.get('source')==source and (v:=canonical(item.get('url',''),source))}
 errors=matched=unresolved=0
 for query,recent in queries:
  try:
   params=dict(engine='google',q=query,api_key=key,hl='zh-TW',gl='tw')
   if recent: params['tbs']='qdr:w'
   r=requests.get('https://serpapi.com/search.json',params=params,timeout=45)
   r.raise_for_status(); result=r.json()
   if result.get('error'): raise ValueError('API error')
   rows=result.get('organic_results',[])
   print(source,query,'organic:',len(rows),flush=True)
   for item in rows:
    if source=='ig':
     author,stale=ig_info(item)
     if not author or stale: continue
    c=resolve(item.get('link'),source)
    if not c: unresolved+=1; continue
    ident,url=c; matched+=1
    if ident in old: continue
    date=''; verified=False
    if source=='x':
     try: stamp=dt.datetime.fromtimestamp(((int(ident)>>22)+1288834974657)/1000,dt.timezone.utc)
     except (ValueError,OverflowError,OSError): continue
     if not now-dt.timedelta(days=7)<=stamp<=now: continue
     date=stamp.isoformat(); verified=True
    add(source,ident,str(item.get('title') or '搜尋候選貼文'),url,date,date_verified=verified,candidate=True)
    old.add(ident)
  except Exception as e:
   errors+=1; print(source,'error:',type(e).__name__,flush=True)
 return f'搜尋候選新增 {counts.get(source,0)} 則；有效網址 {matched} 筆；未解析 {unresolved} 筆；{errors} 次查詢失敗。帳號／照片待確認；零筆不代表沒有新貼文。'

def x(): return social('x', [('site:x.com "설인아"',True),('site:x.com "SEORINA"',True)])
def ig(): return social('ig', [('site:instagram.com/p/ "_seorina"',True),('site:instagram.com/p/ "_seorina"',False)])
for name,fn in [('news',news),('x',x),('ig',ig)]:
 try: status[name]=fn() or '蒐集完成（限來源可取得的資料）'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
