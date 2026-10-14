"""Local legal workspace: Python standard library + SQLite, no pip dependencies."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from http.cookies import SimpleCookie
import sqlite3, hashlib, secrets, json, time, os, webbrowser, threading, datetime, base64, re
from sample_data import sample_data
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'workspace.sqlite3'
DB.parent.mkdir(exist_ok=True)
COLLECTIONS=('cases','clients','tasks','invoices','docs','appointments','evidence')
SESSIONS={}
LOCK=threading.RLock()
def connect():
 c=sqlite3.connect(DB, timeout=20)
 c.execute('PRAGMA foreign_keys=ON')
 return c
with connect() as c:
 c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS records(owner INTEGER NOT NULL, collection TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(owner,collection,id), FOREIGN KEY(owner) REFERENCES users(id))')
 c.execute('CREATE TABLE IF NOT EXISTS revisions(owner INTEGER PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0)')
# Preserve older workspaces that had cases entered without a client-directory record.
with connect() as c:
 for (owner,) in c.execute('SELECT id FROM users').fetchall():
  rows=c.execute('SELECT collection,payload FROM records WHERE owner=?',(owner,)).fetchall()
  clients={json.loads(payload).get('name') for kind,payload in rows if kind=='clients'}
  missing={json.loads(payload).get('client') for kind,payload in rows if kind=='cases'}-clients
  changed=False
  for name in missing:
   if not isinstance(name,str) or not name:continue
   rid=secrets.token_hex(16);record={'id':rid,'name':name,'email':'','phone':''}
   c.execute('INSERT INTO records VALUES(?,?,?,?)',(owner,'clients',rid,json.dumps(record)));changed=True
  if changed:c.execute('UPDATE revisions SET version=version+1 WHERE owner=?',(owner,))
def password(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),310000).hex()
def validate(data):
 if not isinstance(data,dict) or set(data)!=set(COLLECTIONS):raise ValueError('Invalid workspace collections')
 for collection,rows in data.items():
  if not isinstance(rows,list) or len(rows)>10000:raise ValueError('Invalid collection')
  ids=set()
  for row in rows:
   if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or len(row['id'])>80 or not all(x.isalnum() or x in '-_' for x in row['id']):raise ValueError('Invalid record identifier')
   if row['id'] in ids:raise ValueError('Duplicate record identifier')
   ids.add(row['id'])
   if collection=='invoices' and (not isinstance(row.get('amount'),(float,int)) or not 0<=row['amount']<=10**12):raise ValueError('Invalid invoice amount')
   if collection=='docs' and (not isinstance(row.get('data'),str) or not row['data'].startswith('data:') or len(row['data'])>1500000):raise ValueError('Invalid document')
   required={'cases':['title','number','client','court','date','stage','status'],'clients':['name','email','phone'],'tasks':['title','date'],'invoices':['client','description','status'],'docs':['name','date'],'appointments':['title','date','time','location'],'evidence':['title','caseId','type','date','description','documentId']}.get(collection,[])
   if any(not isinstance(row.get(k),str) or len(row[k])>2000 for k in required):raise ValueError('Invalid record fields')
 client_names=[r['name'].strip() for r in data['clients']]
 if len(client_names)!=len(set(client_names)):raise ValueError('Client names must be unique within this workspace')
 for item in data['cases']:
  if item['client'] not in client_names:raise ValueError('Choose an existing client for each case')
  if item['status'] not in ('Active','Closed'):raise ValueError('Invalid case status')
  if not isinstance(item.get('notes',''),str):raise ValueError('Invalid case notes')
  history=item.get('history',[])
  if not isinstance(history,list) or len(history)>1000:raise ValueError('Invalid hearing history')
  for h in history:
   if not isinstance(h,dict) or any(not isinstance(h.get(k),str) or len(h[k])>2000 for k in ('date','stage','notes','nextDate')):raise ValueError('Invalid hearing record')
   datetime.date.fromisoformat(h['date']);datetime.date.fromisoformat(h['nextDate'])
 for kind in ('cases','tasks','appointments','evidence','docs'):
  for item in data[kind]:datetime.date.fromisoformat(item['date'])
 for item in data['tasks']:
  if not isinstance(item.get('done'),bool):raise ValueError('Invalid task completion status')
 for item in data['invoices']:
  if item['client'] not in client_names or item['status'] not in ('Paid','Unpaid'):raise ValueError('Invalid invoice client or status')
 for item in data['appointments']:datetime.time.fromisoformat(item['time'])
 for item in data['docs']:
  try:
   header,payload=item['data'].split(',',1)
   if not header.endswith(';base64'):raise ValueError('Invalid file encoding')
   raw=base64.b64decode(payload,validate=True)
   if len(raw)>1024*1024 or item.get('size')!=len(raw):raise ValueError('Invalid file size')
  except Exception:raise ValueError('Invalid document content')
 case_ids={r['id'] for r in data['cases']}
 doc_ids={r['id'] for r in data['docs']}
 for item in data['evidence']:
  if item['caseId'] not in case_ids:raise ValueError('Evidence must be linked to an existing case')
  if item['documentId'] and item['documentId'] not in doc_ids:raise ValueError('Evidence attachment does not exist')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,data,cookie=None):
  payload=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  if cookie:self.send_header('Set-Cookie',cookie)
  self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def body(self):
  length=int(self.headers.get('Content-Length','0'))
  if length>20*1024*1024:raise ValueError('Workspace exceeds 20 MB request limit')
  return json.loads(self.rfile.read(length))
 def session(self):
  cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie.get('session');s=SESSIONS.get(token.value if token else '')
  return s if s and s['expires']>time.time() else None
 def do_GET(self):
  if self.headers.get('Host') not in ('127.0.0.1:8000','localhost:8000'):return self.send(403,{'error':'Invalid host'})
  if self.path=='/api/bootstrap':
   with connect() as c:exists=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]>0
   s=self.session();return self.send(200,{'registered':exists,'user':{'name':s['name'],'csrf':s['csrf']} if s else None})
  if self.path=='/api/state':
   s=self.session()
   if not s:return self.send(401,{'error':'Sign in required'})
   with connect() as c:
    data={k:[] for k in COLLECTIONS}
    for kind,payload in c.execute('SELECT collection,payload FROM records WHERE owner=? ORDER BY rowid',(s['id'],)):data[kind].append(json.loads(payload))
    version=c.execute('SELECT version FROM revisions WHERE owner=?',(s['id'],)).fetchone()[0]
   return self.send(200,{'data':data,'version':version})
  if self.path in ('/style.css','/app.js'):
   file=ROOT/'static'/self.path[1:];content=file.read_bytes();self.send_response(200);self.send_header('Content-Type','text/css' if self.path.endswith('.css') else 'application/javascript');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
  if self.path in ('/','/index.html'):
   content=(ROOT/'static'/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
  self.send(404,{'error':'Not found'})
 def do_POST(self):
  if self.headers.get('Host') not in ('127.0.0.1:8000','localhost:8000') or self.headers.get('Origin') not in ('http://127.0.0.1:8000','http://localhost:8000'):return self.send(403,{'error':'Invalid request origin'})
  try:
   body=self.body()
   if self.path in ('/api/register','/api/login'):
    email=str(body.get('email','')).strip().lower();p=str(body.get('password',''))
    with LOCK,connect() as c:
     if self.path=='/api/register':
      if c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():return self.send(409,{'error':'This email is already registered. Sign in instead.'})
      name=str(body.get('name','')).strip()
      if not name or len(name)>100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>200 or not 10<=len(p)<=200:raise ValueError('Enter a name, valid email and password of 10–200 characters')
      salt=secrets.token_hex(16);c.execute('INSERT INTO users(name,email,salt,password) VALUES(?,?,?,?)',(name,email,salt,password(p,salt)));uid=c.execute('SELECT last_insert_rowid()').fetchone()[0];c.execute('INSERT INTO revisions(owner) VALUES(?)',(uid,))
      initial=sample_data();validate(initial)
      for kind,rows in initial.items():c.executemany('INSERT INTO records VALUES(?,?,?,?)',[(uid,kind,r['id'],json.dumps(r)) for r in rows])
     row=c.execute('SELECT id,name,salt,password FROM users WHERE email=?',(email,)).fetchone()
     if not row or not secrets.compare_digest(password(p,row[2]),row[3]):return self.send(401,{'error':'Incorrect email or password'})
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);SESSIONS[token]={'id':row[0],'name':row[1],'csrf':csrf,'expires':time.time()+8*3600};return self.send(200,{'name':row[1],'csrf':csrf},'session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
   s=self.session()
   if not s:return self.send(401,{'error':'Sign in required'})
   if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']):return self.send(403,{'error':'Invalid session token'})
   if self.path=='/api/password':
    current=str(body.get('current',''));new=str(body.get('password',''))
    if not 10<=len(new)<=200:raise ValueError('New password must contain 10–200 characters')
    with connect() as c:
     row=c.execute('SELECT salt,password FROM users WHERE id=?',(s['id'],)).fetchone()
     if not secrets.compare_digest(password(current,row[0]),row[1]):return self.send(401,{'error':'Current password is incorrect'})
     salt=secrets.token_hex(16);c.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,password(new,salt),s['id']))
    for token,session in list(SESSIONS.items()):
     if session['id']==s['id'] and session is not s:del SESSIONS[token]
    return self.send(200,{'ok':True})
   if self.path=='/api/logout':
    for token,session in list(SESSIONS.items()):
     if session is s:del SESSIONS[token]
    return self.send(200,{'ok':True},'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   if self.path=='/api/sample':
    with LOCK,connect() as c:
     current=c.execute('SELECT version FROM revisions WHERE owner=?',(s['id'],)).fetchone()[0]
     if body.get('version')!=current:return self.send(409,{'error':'Workspace changed in another tab. Reload before adding sample data.'})
     existing={k:[] for k in COLLECTIONS}
     for kind,payload in c.execute('SELECT collection,payload FROM records WHERE owner=?',(s['id'],)):existing[kind].append(json.loads(payload))
     sample=sample_data();added=[]
     for kind,rows in sample.items():
      ids={r['id'] for r in existing[kind]};names={r['name'] for r in existing['clients']}
      for record in rows:
       if record['id'] in ids or (kind=='clients' and record['name'] in names):continue
       existing[kind].append(record);added.append((s['id'],kind,record['id'],json.dumps(record)))
     validate(existing)
     if added:
      c.executemany('INSERT INTO records VALUES(?,?,?,?)',added);c.execute('UPDATE revisions SET version=version+1 WHERE owner=?',(s['id'],));current+=1
    return self.send(200,{'data':existing,'version':current,'added':len(added)})
   if self.path=='/api/state':
    data=body['data'];validate(data)
    with LOCK,connect() as c:
     current=c.execute('SELECT version FROM revisions WHERE owner=?',(s['id'],)).fetchone()[0]
     if body.get('version')!=current:return self.send(409,{'error':'Workspace changed in another tab. Export your changes, then reload.'})
     c.execute('DELETE FROM records WHERE owner=?',(s['id'],))
     for kind,rows in data.items():
      c.executemany('INSERT INTO records VALUES(?,?,?,?)',[(s['id'],kind,r['id'],json.dumps(r)) for r in rows])
     c.execute('UPDATE revisions SET version=version+1 WHERE owner=?',(s['id'],))
    return self.send(200,{'version':current+1})
   self.send(404,{'error':'Not found'})
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.send(400,{'error':str(e)})
  except Exception:self.send(500,{'error':'Server could not save the request. Check disk availability.'})
if __name__=='__main__':
 try:server=ThreadingHTTPServer(('127.0.0.1',8000),Handler)
 except OSError:raise SystemExit('Port 8000 is occupied. Close the previous workspace server and try again.')
 print('Legal Workspace running at http://127.0.0.1:8000\nKeep this window open. Press Ctrl+C to stop.')
 if '--no-browser' not in __import__('sys').argv:threading.Timer(1,lambda:webbrowser.open('http://127.0.0.1:8000')).start()
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
