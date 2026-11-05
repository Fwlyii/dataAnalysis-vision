"""Run current browser checks; generated evidence stays in ignored artifacts/qa."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,functools,http.server,json,os,subprocess,sys,threading
ROOT=Path(__file__).resolve().parents[1]
SUITES=['coverage','interaction-checks','home-interactions','library-interactions','gateway-checks','intro-checks','resilience','nav-access-checks','lifecycle-checks']
def main():
 p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--port',type=int,default=8848);a=p.parse_args()
 subprocess.run([sys.executable,'scripts/system/build_web_app.py'],cwd=ROOT,check=True)
 class Quiet(http.server.SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',a.port),functools.partial(Quiet,directory=str(ROOT/'app/dist')));threading.Thread(target=server.serve_forever,daemon=True).start()
 env={**os.environ,'BASE_URL':f'http://127.0.0.1:{a.port}/'}
 def run(name):subprocess.run(['node','tests/browser/'+name+'.mjs'],cwd=ROOT,env=env,check=True)
 try:
  if a.full:
   def sequence(names):
    for n in names:run(n)
   with ThreadPoolExecutor(max_workers=3)as pool:
    futures=[pool.submit(run,'coverage'),pool.submit(run,'interaction-checks'),pool.submit(sequence,SUITES[2:])]
    for f in futures:f.result()
  else:run('smoke')
 finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
