"""Manual public-image relay; original bytes and provenance, no labels or tuning.

The GitHub token is used only for this repository's Git blob API. Requests to
external image/page sources contain no authorization, cookies or credentials.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sys
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen

REPO='Quiter53/MaaGakumasuEX-Lab'
HOSTS={'morishimemo.com','appgamelog.com','www.setandset.com','setandset.com','livedoor.blogimg.jp','i0.wp.com','i1.wp.com','i2.wp.com'}
def public(url,referer=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS:
        raise ValueError('Unexpected public source host')
    headers={'User-Agent':'Mozilla/5.0'}
    if referer:headers['Referer']=referer
    with urlopen(Request(url,headers=headers),timeout=30) as response:
        return response.read(),response.headers.get('Content-Type','')
def blob(data):
    expected=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    body=json.dumps({'content':base64.b64encode(data).decode(),'encoding':'base64'}).encode()
    request=Request('https://api.github.com/repos/'+REPO+'/git/blobs',data=body,headers={
        'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'User-Agent':'MaaGakumasuEX-Lab-evaluation','Content-Type':'application/json'})
    with urlopen(request,timeout=60) as response:result=json.load(response)
    assert result['sha']==expected
    return expected
class Images(HTMLParser):
    def __init__(self):super().__init__();self.images=[]
    def handle_starttag(self,tag,attrs):
        if tag!='img':return
        row=dict(attrs);url=row.get('data-src') or row.get('src','')
        try:width,height=int(row.get('width','0')),int(row.get('height','0'))
        except ValueError:return
        if width>=250 and height>=550 and .43<=width/height<=.70:
            self.images.append((url,width,height,row.get('alt','')))
def page_images(page):
    try:
        data,_=public(page['url']);parser=Images();parser.feed(data.decode('utf-8'))
        seen=set();rows=[]
        for url,w,h,alt in parser.images:
            url=urljoin(page['url'],url)
            if url in seen or urlsplit(url).hostname not in HOSTS:continue
            seen.add(url);rows.append({'url':url,'declaredSize':[w,h],'alt':alt})
        return [dict(row,id=page['id']+'-'+str(i),group=page['group'],page=page['url'])
                for i,row in enumerate(rows[-26:])]
    except Exception as error:
        print('Page unavailable: '+page['id']+' '+type(error).__name__,flush=True);return []
def collect(row):
    try:
        data,kind=public(row['url'],row['page'])
        if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):
            raise ValueError('Not a PNG/JPEG source image')
        return dict(row,sizeBytes=len(data),sha256=hashlib.sha256(data).hexdigest(),gitBlob=blob(data))
    except Exception as error:return dict(row,error=type(error).__name__)
def main():
    config=json.loads(Path(sys.argv[1]).read_text('utf-8'))
    rows=[]
    for page in config['pages']:rows.extend(page_images(page))
    records=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(collect,rows):
            records.append(result);print(json.dumps({k:result[k] for k in ('id','gitBlob','error') if k in result}),flush=True)
    result={'scope':__doc__,'labelsVerified':False,'sourcePages':config['pages'],'records':records}
    sha=blob(json.dumps(result,ensure_ascii=False,indent=2).encode())
    print('RESULT_MANIFEST_BLOB='+sha,flush=True)
    print(json.dumps({'downloaded':sum('gitBlob' in r for r in records),'failed':sum('error' in r for r in records)}),flush=True)
if __name__=='__main__':main()
