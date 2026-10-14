"""Run: python tests/test_app.py. Uses a temporary database, not your records."""
import subprocess,sys,time,urllib.request,urllib.error,http.cookiejar,json,tempfile,shutil,sqlite3
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]
class Client:
 def __init__(self):self.csrf='';self.jar=http.cookiejar.CookieJar();self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
 def call(self,path,data=None,origin='http://127.0.0.1:8000'):
  headers={'Origin':origin,'Content-Type':'application/json','X-CSRF-Token':self.csrf}
  req=urllib.request.Request('http://127.0.0.1:8000'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
  try:
   with self.http.open(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def signup(self,email):
  status,data=self.call('/api/register',{'name':'Test Advocate','email':email,'password':'secure-pass-123'});assert status==200,(status,data);self.csrf=data['csrf']
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);shutil.copy(SOURCE/'app.py',root);shutil.copy(SOURCE/'sample_data.py',root);shutil.copytree(SOURCE/'static',root/'static')
 def boot():
  p=subprocess.Popen([sys.executable,str(root/'app.py'),'--no-browser'],stdout=subprocess.DEVNULL)
  for _ in range(50):
   if p.poll() is not None:raise RuntimeError('Port 8000 is occupied. Stop your app before running tests.')
   try:urllib.request.urlopen('http://127.0.0.1:8000/api/bootstrap');return p
   except:time.sleep(.1)
  p.terminate();raise RuntimeError('Server failed to start')
 p=boot()
 try:
  a,b=Client(),Client();assert a.call('/api/state')[0]==401
  assert a.call('/api/register',{'name':'Test','email':'test@example.test','password':'secure-pass-123'},'https://other.test')[0]==403
  a.signup('first@example.test');b.signup('second@example.test')
  assert a.call('/api/register',{'name':'Duplicate','email':'first@example.test','password':'secure-pass-123'})[0]==409
  empty=a.call('/api/state')[1]['data'];assert len(empty['cases'])==6 and len(empty['evidence'])==4
  data={k:[] for k in empty}
  data['clients']=[dict(id='client-1',name='Test Client',email='client@example.test',phone='1234567890')]
  data['cases']=[dict(id='case-1',title='Test Client vs. Horizon',number='CS-001',client='Test Client',court='District Court',date='2026-10-14',stage='Arguments',status='Active',notes='Saved note')]
  data['appointments']=[dict(id='appt-1',title='Consultation',date='2026-10-15',time='10:00',location='Office')]
  data['tasks']=[dict(id='task-1',title='Prepare submissions',date='2026-10-15',done=False)]
  data['invoices']=[dict(id='invoice-1',client='Test Client',description='Drafting',amount=1500,status='Unpaid')]
  data['docs']=[dict(id='doc-1',name='evidence.txt',date='2026-10-14',size=5,data='data:text/plain;base64,aGVsbG8=')]
  data['evidence']=[dict(id='evidence-1',caseId='case-1',title='Exhibit A',type='Document',date='2026-10-14',description='Original document',documentId='doc-1')]
  assert a.call('/api/state',{'data':data,'version':0})==(200,{'version':1})
  assert all(r['id']!='case-1' for r in b.call('/api/state')[1]['data']['cases']),'Account data leaked'
  assert a.call('/api/state',{'data':data,'version':0})[0]==409
  broken=json.loads(json.dumps(data));broken['evidence'][0]['caseId']='missing';assert a.call('/api/state',{'data':broken,'version':1})[0]==400
  broken=json.loads(json.dumps(data));broken['docs'][0]['size']=999;assert a.call('/api/state',{'data':broken,'version':1})[0]==400
  wrong=a.csrf;a.csrf='wrong';assert a.call('/api/state',{'data':data,'version':1})[0]==403;a.csrf=wrong
  data['cases'][0]['history']=[dict(date='2026-10-14',nextDate='2026-11-03',stage='Evidence',notes='Hearing recorded')];data['cases'][0]['date']='2026-11-03';data['cases'][0]['stage']='Evidence';data['tasks'][0]['done']=True;data['invoices'][0]['status']='Paid'
  assert a.call('/api/state',{'data':data,'version':1})==(200,{'version':2})
  assert a.call('/api/state')[1]['data']==data
  assert a.call('/api/password',{'current':'wrong','password':'updated-pass-123'})[0]==401
  assert a.call('/api/password',{'current':'secure-pass-123','password':'updated-pass-123'})[0]==200
  assert a.call('/api/logout',{})[0]==200;assert a.call('/api/state')[0]==401
  p.terminate();p.wait();p=boot();a=Client()
  assert a.call('/api/login',{'email':'first@example.test','password':'secure-pass-123'})[0]==401
  status,res=a.call('/api/login',{'email':'first@example.test','password':'updated-pass-123'});assert status==200;a.csrf=res['csrf']
  assert a.call('/api/state')[1]['data']==data,'Records lost after restart'
  with sqlite3.connect(root/'data'/'workspace.sqlite3') as c:
   assert c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==2
   assert c.execute('SELECT COUNT(*) FROM records WHERE owner=1').fetchone()[0]==7
   assert c.execute('SELECT password FROM users LIMIT 1').fetchone()[0]!='updated-pass-123'
  before=a.call('/api/state')[1]
  code,loaded=a.call('/api/sample',{'version':before['version']});assert code==200 and loaded['added']==31
  assert any(r['id']=='case-1' for r in loaded['data']['cases'])
  code,again=a.call('/api/sample',{'version':loaded['version']});assert code==200 and again['added']==0
  assert len(again['data']['cases'])==7 and len(again['data']['evidence'])==5
  for asset in ('/','/style.css','/app.js'):
   assert urllib.request.urlopen('http://127.0.0.1:8000'+asset).status==200
  print('PASS: signup/login, two-account isolation, duplicate signup rejection, CSRF/origin checks, cases, clients, tasks, appointments, billing, files, evidence links, hearing history, invalid data rejection, concurrent edit protection, password change, logout and database persistence after restart.')
 finally:p.terminate();p.wait()
