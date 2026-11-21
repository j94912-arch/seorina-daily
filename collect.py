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

def unwrap(href):
 u=urlsplit(href); q=parse_qs(u.query)
 if u.path=='/url': return q.get('q',q.get('url',['']))[0]
 if u.path.startswith('/ck/a') and 'u' in q:
  v=q['u'][0]
  if v.startswith('a1'):
   try: return base64.urlsafe_b64decode(v[2:]+'='*(-len(v[2:])%4)).decode()
   except Exception: return ''
 return href

def social(source,queries):
 errors=0; matched=0; empty=0
 old={v[0] for item in data['items'] if item.get('source')==source and (v:=canonical(item.get('url',''),source))}
 for engine,query,recent in queries:
  try:
   params={'q':query,'hl':'zh-TW'} if engine=='google' else {'q':query,'setlang':'zh-hant'}
   if recent and engine=='google': params['tbs']='qdr:w'
   r=requests.get('https://www.google.com/search' if engine=='google' else 'https://www.bing.com/search',params=params,headers={'User-Agent':'Mozilla/5.0'},timeout=25)
   print(f'{source} {engine} {query}: HTTP {r.status_code}; bytes={len(r.content)}; final={r.url}; hash={hashlib.sha256(r.content).hexdigest()[:12]}',flush=True)
   r.raise_for_status()
   low=r.text.lower()
   if 'unusual traffic' in low or '/sorry/' in r.url or 'consent.google.com' in r.url: raise ValueError('challenge_or_consent')
   parser=Links(); parser.feed(r.text)
   links=[(unwrap(h),t) for h,t in parser.links]
   found={}
   for href,title in links:
    c=canonical(href,source)
    if c: found[c[0]]=(c[1],title.strip())
   print(f'anchors={len(links)}; matched={len(found)}; page_title={re.findall(r"<title[^>]*>(.*?)</title>",r.text,re.I|re.S)[:1]}',flush=True)
   if not found: empty+=1
   matched+=len(found)
   for ident,(url,title) in found.items():
    if ident in old: continue
    date=''; verified=False
    if source=='x':
     try:
      stamp=dt.datetime.fromtimestamp(((int(ident)>>22)+1288834974657)/1000,dt.timezone.utc)
      if not (now-dt.timedelta(days=7)<=stamp<=now): continue
      date=stamp.isoformat(); verified=True
     except (ValueError,OverflowError,OSError): continue
    else:
     # Require explicit author wording in result title; still a candidate, not proof.
     if not re.search(r'(?i)(?:photos? by|videos? by|reels? by|posted by).*?\(@_seorina\)',title):
      print('IG author unconfirmed:',ident,repr(title[:120]),flush=True)
      continue
    add(source,ident,title or '搜尋候選貼文',url,date,date_verified=verified,candidate=True)
    old.add(ident)
  except Exception as e:
   errors+=1; print(source,engine,type(e).__name__,str(e)[:200],flush=True)
 return f'搜尋候選新增 {counts.get(source,0)} 則；命中 {matched} 筆；{empty} 次零命中；{errors} 次查詢失敗。結果不完整，帳號／照片待確認；零筆不代表沒有新貼文。'

def x(): return social('x',[(e,q,True) for e in ('google','bing') for q in ('site:x.com "설인아"','site:x.com "SEORINA"','site:twitter.com "설인아"')])
def ig(): return social('ig',[(e,q,w) for e in ('google','bing') for q in ('site:instagram.com/p/ "_seorina"','site:instagram.com/reel/ "_seorina"') for w in ((True,False) if e=='google' else (False,))])
for name,fn in [('news',news),('x',x),('ig',ig)]:
 try: status[name]=fn() or '蒐集完成（限來源可取得的資料）'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
