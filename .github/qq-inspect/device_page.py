"""Read public QQ device-name page assets; never send account credentials or writes."""
import json,re,urllib.request,urllib.parse
def read(url):
    host=urllib.parse.urlsplit(url).hostname or ""
    if not (host.endswith(".qq.com") or host.endswith(".gtimg.cn") or host.endswith(".qpic.cn")):
        raise ValueError("unexpected asset host")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 QQ/9.3.86"})
    with urllib.request.urlopen(req,timeout=25) as response:
        data=response.read(3*1024*1024+1)
        if len(data)>3*1024*1024: raise ValueError("asset size limit")
        return data.decode("utf-8",errors="replace")
url="https://club.vip.qq.com/onlinestatus/set?_wv=67109895&_wvx=10&_proxy=1"
try:
    page=read(url)
    print("QQ_DEVICE_PAGE "+json.dumps({"bytes":len(page),"title":re.findall(r"<title>(.*?)</title>",page)}))
    scripts=re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)',page,re.I)
    print("QQ_DEVICE_ASSETS "+json.dumps(scripts[:15]))
    for source in scripts[:15]:
        asset=urllib.parse.urljoin(url,source)
        try:
            code=read(asset)
            matches=list(re.finditer(r"customDevice|deviceName|device_name|setModel|modelName|model_name|setDevice|SetDevice|onlinestatus|自定义设备",code,re.I))
            snippets=[code[max(0,m.start()-160):m.end()+240] for m in matches[:25]]
            if snippets: print("QQ_DEVICE_CODE "+json.dumps({"asset":asset,"snippets":snippets},ensure_ascii=True))
        except Exception as exc: print("QQ_DEVICE_ASSET_FAILED "+type(exc).__name__)
except Exception as exc:
    print("QQ_DEVICE_PAGE_UNAVAILABLE "+type(exc).__name__)
