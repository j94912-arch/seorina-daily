import os,json,datetime as dt, requests, feedparser
from pathlib import Path
from pywebpush import webpush
from zoneinfo import ZoneInfo
P=Path('docs/data.json'); now=dt.datetime.now(ZoneInfo('Asia/Taipei')); day=now.date()-dt.timedelta(days=1)
start=dt.datetime.combine(day,dt.time.min,now.tzinfo); end=start+dt.timedelta(days=1)
data=json.loads(P.read_text()) if P.exists() else {'items':[]}; seen={x['id'] for x in data['items']}; status={}; counts={}
def add(source,id,title,url,date):
 id=source+':'+str(id)
 if id not in seen:
  seen.add(id); data['items'].append(dict(source=source,id=id,title=title,url=url,date=date,batch=str(now.date()))); counts[source]=counts.get(source,0)+1

def get(url,**kw):
 r=requests.get(url,timeout=35,**kw); r.raise_for_status(); return r.json()
def news():
 r=requests.get('https://news.google.com/rss/search',params={'q':'설인아 when:7d','hl':'ko','gl':'KR','ceid':'KR:ko'},timeout=35); r.raise_for_status(); f=feedparser.parse(r.content)
 if f.bozo and not f.entries: raise ValueError('RSS parse error')
 for e in f.entries:
  add('news',e.get('id',e.link),e.title,e.link,e.get('published',''))
def x():
 token=os.getenv('X_BEARER_TOKEN');
 if not token: return '尚未設定 X API；未檢查'
 params={'query':'(#설인아 OR #SEORINA)','start_time':start.isoformat(),'end_time':end.isoformat(),'max_results':100,'tweet.fields':'created_at'}
 while True:
  j=get('https://api.x.com/2/tweets/search/recent',params=params,headers={'Authorization':'Bearer '+token})
  if j.get('errors'): raise ValueError('X API partial error')
  for t in j.get('data',[]): add('x',t['id'],t['text'],'https://x.com/i/web/status/'+t['id'],t['created_at'])
  token2=j.get('meta',{}).get('next_token')
  if not token2: break
  params['next_token']=token2

def ig():
 token=os.getenv('IG_ACCESS_TOKEN'); uid=os.getenv('IG_USER_ID'); version=os.getenv('META_GRAPH_VERSION')
 if not all((token,uid,version)): return '尚未設定 Meta Business Discovery；未檢查'
 j=get(f'https://graph.facebook.com/{version}/{uid}',params={'fields':'business_discovery.username(_seorina){media.limit(50){id,caption,permalink,timestamp}}','access_token':token})
 media=j['business_discovery']['media']
 while True:
  for m in media.get('data',[]):
   if dt.datetime.fromisoformat(m['timestamp'].replace('Z','+00:00')) >= now-dt.timedelta(days=7): add('ig',m['id'],m.get('caption','Instagram 貼文'),m['permalink'],m['timestamp'])
  nxt=media.get('paging',{}).get('next')
  if not nxt: break
  media=get(nxt)
  if media.get('data') and dt.datetime.fromisoformat(media['data'][-1]['timestamp'].replace('Z','+00:00')) < now-dt.timedelta(days=7):
   for m in media['data']:
    if dt.datetime.fromisoformat(m['timestamp'].replace('Z','+00:00')) >= now-dt.timedelta(days=7): add('ig',m['id'],m.get('caption','Instagram 貼文'),m['permalink'],m['timestamp'])
   break
for name,fn in [('news',news),('x',x),('ig',ig)]:
 try: status[name]=fn() or '蒐集完成（限來源可取得的資料）'
 except Exception as e: status[name]='蒐集失敗或不完整：'+type(e).__name__
data.update(updated=now.isoformat(),target=str(day),status=status,counts=counts); P.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
