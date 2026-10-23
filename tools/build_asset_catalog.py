"""Build a searchable offline browser and tabular index from export manifests."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "game-assets"

PAGE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>游戏原始素材 · EX Lab</title>
<style>
body{margin:0;background:#161b22;color:#e6edf3;font:15px system-ui,sans-serif}header{padding:24px;position:sticky;top:0;background:#161b22;z-index:1;border-bottom:1px solid #39414b}h1{margin:0 0 10px;font-size:23px}input,select,button{padding:10px;border:1px solid #586473;border-radius:6px;background:#222a35;color:#fff;font:inherit}input{width:min(50vw,520px)}#status{margin-top:12px;color:#aeb9c7}.grid{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}article{border:1px solid #39414b;border-radius:8px;overflow:hidden}article img{width:100%;height:185px;object-fit:contain;background:repeating-conic-gradient(#30363d 0% 25%,#242a32 0% 50%) 50%/20px 20px;display:block}article a{color:inherit;text-decoration:none}article p{margin:10px;overflow-wrap:anywhere;font-size:13px}small{color:#aeb9c7}footer{padding:0 24px 24px;display:flex;gap:12px;align-items:center}
</style>
<header><h1>游戏原始素材 · EX Lab</h1><input id="query" placeholder="搜索资源名、卡名或文件路径" aria-label="搜索素材">
<select id="category" aria-label="素材类型"><option value="all">全部素材</option><option value="cards">卡图</option><option value="drinks">饮料</option><option value="ui-sprite">界面 Sprite</option><option value="ui-texture">完整纹理 / 图集</option></select><div id="status" role="status"></div></header>
<main class="grid" id="grid"></main><footer><button id="previous">上一页</button><span id="page"></span><button id="next">下一页</button></footer>
<script id="catalog" type="application/json">__CATALOG__</script>
<script>
const rows=JSON.parse(document.getElementById('catalog').textContent);let page=0;const size=60;
const query=document.getElementById('query'),category=document.getElementById('category');
function draw(){const term=query.value.trim().toLocaleLowerCase();const found=rows.filter(r=>(category.value==='all'||r.category===category.value)&&[r.name,r.path,...r.cardNames].join(' ').toLocaleLowerCase().includes(term));const pages=Math.max(1,Math.ceil(found.length/size));page=Math.max(0,Math.min(page,pages-1));const grid=document.getElementById('grid');grid.replaceChildren();for(const r of found.slice(page*size,(page+1)*size)){const box=document.createElement('article'),a=document.createElement('a'),img=document.createElement('img'),title=document.createElement('p'),info=document.createElement('p');a.href=encodeURI(r.path);a.target='_blank';a.rel='noopener';img.src=encodeURI(r.path);img.loading='lazy';img.alt=r.name;title.textContent=r.cardNames.length?r.cardNames.join(' / '):r.name;info.textContent=r.width+' × '+r.height+' · '+r.name;info.style.color='#aeb9c7';a.append(img,title);box.append(a,info);grid.append(box)}document.getElementById('status').textContent='找到 '+found.length+' 项 / 共 '+rows.length+' 项；点击图片查看原尺寸 PNG';document.getElementById('page').textContent=(page+1)+' / '+pages;document.getElementById('previous').disabled=page===0;document.getElementById('next').disabled=page>=pages-1}
query.addEventListener('input',()=>{page=0;draw()});category.addEventListener('change',()=>{page=0;draw()});document.getElementById('previous').onclick=()=>{page--;draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();
</script></html>
'''


def main():
    rows = []
    cards = json.loads((ROOT / "card-drink-manifest.json").read_text("utf-8"))
    ui = json.loads((ROOT / "ui/manifest.json").read_text("utf-8"))
    for item in cards["files"]:
        rows.append(dict(path=item["path"], name=item["assetName"], category=item["category"],
            cardNames=sorted({card["name"] for card in item["cards"]}),
            width=item["size"][0], height=item["size"][1], sha256=item["sha256"]))
    for item in ui["files"]:
        rows.append(dict(path="ui/"+item["path"], name=item["name"],
            category="ui-sprite" if item["type"] == "Sprite" else "ui-texture", cardNames=[],
            width=item["size"][0], height=item["size"][1], sha256=item["sha256"]))
    rows.sort(key=lambda r:(r["category"], r["name"], r["path"]))
    (ROOT / "catalog.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n","utf-8")
    with (ROOT / "catalog.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["path","name","category","cardNames","width","height","sha256"])
        writer.writeheader()
        writer.writerows({**r,"cardNames":" / ".join(r["cardNames"])} for r in rows)
    payload=json.dumps(rows,ensure_ascii=False).replace("<", "\\u003c")
    (ROOT / "index.html").write_text(PAGE.replace("__CATALOG__",payload),"utf-8")
    print(f"Indexed {len(rows)} original images.")


if __name__ == "__main__":
    main()
