import os,json,datetime as dt, requests, feedparser
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs
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
class Links(HTMLParser):
 def __init__(self):
  super().__init__(); self.links=[]; self.current=None
 def handle_starttag(self,tag,attrs):
  if tag=='a': self.current=[dict(attrs).get('href',''),'']
 def handle_data(self,text):
  if self.current is not None: self.current[1]+=text
 def handle_endtag(self,tag):
  if tag=='a' and self.current is not None:
   self.links.append(self.current); self.current=None

def canonical(url,source):
 u=urlsplit(url); host=(u.hostname or '').lower(); path=u.path
 if source=='ig' and host in ('instagram.com','www.instagram.com'):
  m=re.fullmatch(r'/(?:p|reel)/([A-Za-z0-9_-]+)/?',path)
  if m: return m[1], 'https://www.instagram.com'+path.rstrip('/')+'/'
 if source=='x' and host in ('x.com','www.x.com','twitter.com','www.twitter.com'):
  m=re.match(r'/[^/]+/status/(\d+)(?:/|$)',path) or re.match(r'/i/web/status/(\d+)(?:/|$)',path)
  if m: return m[1], 'https://x.com/i/web/status/'+m[1]
 return None

def social(source,queries):
 errors=0; matched=0
 old={v[0] for item in data['items'] if item.get('source')==source and (v:=canonical(item.get('url',''),source))}
 for query in queries:
  try:
   r=requests.get('https://www.google.com/search',params={'q':query,'tbs':'qdr:w','hl':'ko'},headers={'User-Agent':'Mozilla/5.0'},timeout=25); r.raise_for_status()
   if 'unusual traffic' in r.text.lower() or '/sorry/' in r.url: raise ValueError('blocked')
   parser=Links(); parser.feed(r.text)
   for href,title in parser.links:
    u=urlsplit(href)
    if u.path=='/url': href=parse_qs(u.query).get('q',parse_qs(u.query).get('url',['']))[0]
    c=canonical(href,source)
    if not c: continue
    matched+=1; ident,url=c
    if ident in old: continue
    # Search result dates and captions are not authoritative.
    date=''; verified=False
    if source=='x':
     try:
      stamp=dt.datetime.fromtimestamp(((int(ident)>>22)+1288834974657)/1000,dt.timezone.utc)
      if not (now-dt.timedelta(days=7)<=stamp<=now): continue
      date=stamp.isoformat(); verified=True
     except (ValueError,OverflowError,OSError): continue
    add(source,ident,title.strip() or ('Instagram 搜尋候選貼文' if source=='ig' else 'X 搜尋候選貼文'),url,date,date_verified=verified,candidate=True)
    old.add(ident)
  except Exception as e:
   errors+=1; print(source,type(e).__name__)
 return f'搜尋候選新增 {counts.get(source,0)} 則；命中 {matched} 筆；{errors} 次查詢失敗。結果不完整，帳號／照片待確認；零筆不代表沒有新貼文。'

def x(): return social('x',['site:x.com "#설인아" photo','site:x.com "#SEORINA" photo','site:twitter.com "설인아" photo'])
def ig(): return social('ig',['site:instagram.com/p/ "_seorina"','site:instagram.com/reel/ "_seorina"'])
for name,fn in [('news',news),('x',x),('ig',ig)]:
 try: status[name]=fn() or '蒐集完成（限來源可取得的資料）'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
