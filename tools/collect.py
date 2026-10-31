#!/usr/bin/env python3
"""세웅지씨·커피리브레·GSC 생두 목록을 모아 앱의 data/market.json으로 만든다.

- 가격은 모두 1kg 기준(세웅지씨·GSC는 1kg 옵션, 커피리브레는 「생두소분」 1kg 상품)으로 통일한다.
- 세웅지씨 「생두찾기」의 필터(구매정보·등급·품종·가공·농장)로 각 상품의 판매처 분류를 그대로 가져오고,
  향미 분류(생두찾기의 향미 항목과 동의어)는 세 판매처의 컵 노트에 같은 기준으로 붙인다.
- 표준 라이브러리만 쓴다. 판매처 서버에 부담을 주지 않도록 요청 사이에 쉬어 간다.

사용: python tools/market/collect.py [출력 경로]   (기본 data/market.json)
"""
import gzip, html, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
PAUSE = 0.35
SW, LB, GSC = "https://www.sewoonggc.com", "https://coffeelibre.kr", "https://gsc.coffee"
SOURCES = {
    "sw": {"name": "세웅지씨", "url": SW + "/goods/beans_search.php", "ship": {"fee": 3500, "free": 50000}},
    "lb": {"name": "커피리브레", "url": LB + "/category/%EC%83%9D%EB%91%90%EC%86%8C%EB%B6%84/57/", "ship": {"fee": 3000, "free": 40000}},
    "gsc": {"name": "GSC", "url": GSC + "/goods/goods_list.php?cateCd=014", "ship": {"fee": 3500, "free": 50000}},
}
COUNTRIES = ["에티오피아", "케냐", "탄자니아", "르완다", "부룬디", "우간다", "콩고", "과테말라", "브라질", "엘살바도르", "온두라스", "자메이카", "코스타리카",
             "콜롬비아", "멕시코", "하와이", "파나마", "니카라과", "페루", "볼리비아", "에콰도르", "도미니카", "인도네시아", "인도", "베트남", "파푸아뉴기니",
             "예멘", "라오스", "태국", "미얀마", "중국"]
EN_COUNTRY = {"ethiopia": "에티오피아", "kenya": "케냐", "tanzania": "탄자니아", "rwanda": "르완다", "burundi": "부룬디", "guatemala": "과테말라",
              "brazil": "브라질", "el salvador": "엘살바도르", "honduras": "온두라스", "jamaica": "자메이카", "costa rica": "코스타리카", "colombia": "콜롬비아",
              "mexico": "멕시코", "hawaii": "하와이", "panama": "파나마", "nicaragua": "니카라과", "peru": "페루", "indonesia": "인도네시아", "india": "인도",
              "vietnam": "베트남", "papua new guinea": "파푸아뉴기니", "png": "파푸아뉴기니", "yemen": "예멘"}
# 판매처 등급 이름 → 세웅지씨 생두찾기 등급 분류(GSC 컨벤셔널·프리미엄은 같은 위치의 이름으로 잇는다)
TIER = {"커머셜": "커머셜", "컨벤셔널": "커머셜", "하이커머셜": "하이커머셜", "프리미엄": "하이커머셜", "스페셜티": "스페셜티", "마이크로랏": "마이크로랏"}


def get(url, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "ko-KR,ko"})
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
            time.sleep(PAUSE)
            return b.decode("utf-8", "ignore")
        except Exception as e:  # 잠깐 쉬고 다시
            if k == tries - 1:
                print("  실패:", url, e, file=sys.stderr)
                return ""
            time.sleep(2)


BLOCK = r"br|p|div|li|tr|td|th|dt|dd|h[1-6]|option|button|ul|ol|table|section|article|strong"


def text_lines(h):
    """HTML → 줄 목록(브라우저 innerText와 비슷하게: 블록 경계마다 줄바꿈)."""
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<(?:/?(?:" + BLOCK + r"))\b[^>]*>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    return [re.sub(r"[ \t ​]+", " ", l).strip() for l in h.split("\n") if l.strip()]


def norm_label(s):
    return re.sub(r"^\d{1,2}\.\s*", "", s).replace(" ", "")


def label(lines, names):
    """「라벨 : 값」 또는 라벨 다음 줄의 값."""
    for n in [names] if isinstance(names, str) else names:
        key = n.replace(" ", "")
        for i, l in enumerate(lines):
            m = re.match(r"^(?:\d{1,2}\.\s*)?(.+?)\s*[:：]\s*(.+)$", l)
            if m and m.group(1).replace(" ", "") == key:
                return m.group(2).strip()
            if norm_label(l) == key and i + 1 < len(lines) and not re.match(r"^\d{1,2}\.\s*[가-힣A-Za-z]", lines[i + 1]):
                return lines[i + 1].strip()
    return ""


def proc_key(s):
    s = (s or "").lower()
    if re.search(r"무산소|어내로빅|언에어로빅|아나에로빅|anaerob|\basd\b|카보닉|carbonic", s): return "무산소"
    if re.search(r"허니|honey", s): return "허니"
    if re.search(r"내추럴|네추럴|natural|건식|펄프드", s): return "내추럴"
    if re.search(r"워시드|washed|수세|wet hulled|길링", s): return "워시드"
    if re.search(r"디카페인|decaf|swiss water|마운틴워터", s): return "디카페인"
    return "기타"


def country_of(*texts):
    t = " ".join(x or "" for x in texts)
    for c in COUNTRIES:
        if c in t: return c
    tl = t.lower()
    for e, c in EN_COUNTRY.items():
        if e in tl: return c
    return ""


def altitude(s):
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", s or "")]
    nums = [n for n in nums if 300 <= n <= 3000]
    return [min(nums), max(nums)] if nums else None


def year_of(*texts):
    """상품명의 연도 표기(2026 등). 「산타 테레사 2000」처럼 고도·로트 숫자와 헷갈리지 않게 최근 연도만, 여럿이면 가장 큰 값."""
    now = datetime.now().year
    for t in texts:
        ys = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", t or "") if 2015 <= int(y) <= now + 1]
        if ys: return max(ys)
    return None


def won(s):
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,7})\s*원", s or "")
    return int(m.group(1).replace(",", "")) if m else None


# ---------------- 세웅지씨 ----------------
def sw_result_ids(h):
    i = h.find("goods_list_cont")
    if i < 0: return []
    j = h.find("pagination", i)
    part = h[i: j if j > 0 else len(h)]
    return list(dict.fromkeys(re.findall(r"goods_view\.php\?goodsNo=(\d+)", part)))


def sw_search(params):
    """생두찾기 검색 결과의 상품 번호 전부(페이지 넘김)."""
    ids, page = [], 1
    while page < 30:
        q = urllib.parse.urlencode(params + [("page", page)], doseq=True)
        got = sw_result_ids(get(SW + "/goods/beans_search.php?" + q))
        new = [x for x in got if x not in ids]
        if not new: break
        ids += new; page += 1
    return ids


def sw_filters():
    """생두찾기 화면의 필터 그룹: {그룹 번호: (그룹 이름, [(값, 표시 글)])}"""
    h = get(SW + "/goods/beans_search.php")
    groups = {}
    for m in re.finditer(r'search_filter_title">([^<]+)<span>.*?search_filter_contents">(.*?)</div>', h, re.S):
        title = m.group(1).strip()
        opts = re.findall(r'name="searchFilter\[(\d+)\]\[\]" value="([^"]+)"\s*>([^<]*)<', m.group(2))
        for g, v, lab in opts:
            groups.setdefault(int(g), (title, []))[1].append((html.unescape(v), html.unescape(lab).strip()))
    return groups


def sw_detail(no, list_name):
    h = get(f"{SW}/goods/goods_view.php?goodsNo={no}")
    L = text_lines(h)
    name = list_name
    m = re.search(r'<meta property="og:title" content="([^"]+)"', h)
    if m and not name: name = html.unescape(m.group(1))
    # 1kg 옵션의 판매가: 기본 옵션이 1kg이고 추가금 0이면 판매가 그대로
    opts = re.findall(r'<option[^>]*value="\d+\|\|(\d+)\|\|[^"]*\^\|\^([^"]+)"', h)
    price = None
    i = next((k for k, l in enumerate(L) if l == "판매가"), -1)
    if i >= 0:
        price = won(" ".join(L[i + 1:i + 4]))
    unit = "1kg"
    if opts and not any(o[1].strip().lower().startswith("1kg") and o[0] == "0" for o in opts):
        unit = opts[0][1].strip()
    scores = {}
    k = next((k for k, l in enumerate(L) if l == "컵 프로파일"), -1)
    if k >= 0:
        for a in range(k + 1, min(k + 14, len(L) - 1)):
            if L[a] in ("향미", "산미", "단맛", "바디감", "밸런스") and re.match(r"^\d(\.\d)?$", L[a + 1]):
                scores[L[a]] = float(L[a + 1])
    ny = label(L, ["국가/수확년도"])
    mv = label(L, ["수분율/밀도"])
    mm = re.search(r"(\d+(?:\.\d+)?)\s*%", mv)
    gl = re.search(r"(\d{3}(?:\.\d+)?)\s*g\s*/\s*l", mv, re.I)
    sold = bool(re.search(r"(?i)out of stock|>\s*품절\s*<|btn_soldout|item_soldout", h[: h.find("상세정보") if "상세정보" in h else len(h)]))
    return {
        "name": name, "price": price, "unit": unit, "soldOut": sold,
        "country": country_of(label(L, "원산지"), ny, name), "region": label(L, ["생산지역", "지역"]),
        "farm": label(L, "농장"), "variety": label(L, "품종"), "process": label(L, "가공방식"),
        "grade": label(L, "등급"), "alt": altitude(label(L, "재배고도")), "harvest": year_of(ny, name),
        "cup": label(L, ["커핑 노트", "플레이버 노트"]), "roast": label(L, "로스팅"),
        "moisture": float(mm.group(1)) if mm else None, "densityGL": float(gl.group(1)) if gl else None,
        "scores": scores or None,
    }


def collect_sw():
    print("세웅지씨: 생두찾기 전체 목록", file=sys.stderr)
    names, ids, page = {}, [], 1
    while page < 30:
        h = get(f"{SW}/goods/beans_search.php?page={page}")
        got = sw_result_ids(h)
        for no, nm in re.findall(r'goods_view\.php\?goodsNo=(\d+)"[^>]*>\s*<img[^>]*alt="([^"]*)"', h):
            names.setdefault(no, html.unescape(nm))
        new = [x for x in got if x not in ids]
        if not new: break
        ids += new; page += 1
    print(f"  {len(ids)}개", file=sys.stderr)
    groups = sw_filters()
    tags = {no: {} for no in ids}
    for g, (title, opts) in groups.items():
        if g == 6: continue  # 향미는 컵 노트 글로 분류(세 판매처 공통 기준)
        for v, lab in opts:
            for no in sw_search([(f"searchFilter[{g}][]", v)]):
                if no in tags: tags[no].setdefault(title, []).append(v)
        print(f"  필터 {title}: {len(opts)}개 값", file=sys.stderr)
    items = []
    for n, no in enumerate(ids, 1):
        d = sw_detail(no, names.get(no, ""))
        t = tags.get(no, {})
        info = t.get("구매정보 ", t.get("구매정보", []))
        items.append(base_item("sw", no, f"{SW}/goods/goods_view.php?goodsNo={no}", d, {
            "swTags": t, "tier": next((TIER[x] for x in t.get("등급 ", t.get("등급", [])) if x in TIER), None),
            "isNew": any(x in ("신규입고", "재입고") for x in info), "sale": "세일" in info, "comingSoon": "입고예정" in info}))
        if n % 20 == 0: print(f"  상세 {n}/{len(ids)}", file=sys.stderr)
    return items, groups


# ---------------- 커피리브레 (생두소분 1kg) ----------------
def collect_lb():
    print("커피리브레: 생두소분(1kg) 목록", file=sys.stderr)
    h = get(SOURCES["lb"]["url"])
    items = []
    blocks = re.findall(r'<li id="anchorBoxId_(\d+)"(.*?)(?=<li id="anchorBoxId_|</ul>\s*</div>\s*<div class="xans-element- xans-product xans-product-normalpaging)', h, re.S)
    print(f"  {len(blocks)}개", file=sys.stderr)
    for n, (no, b) in enumerate(blocks, 1):
        nm = re.search(r'<strong><a href="[^"]*"[^>]*>(.*?)</a>', b, re.S)
        raw = html.unescape(re.sub(r"<[^>]+>", " ", nm.group(1))) if nm else ""
        raw = re.sub(r"\s+", " ", raw).strip()
        L = text_lines(b)
        price = next((won(l) for l in L if won(l)), None)
        notes = next((l for l in L if l.count(",") >= 2 and not won(l)), "")
        sold = bool(re.search(r'class="soldOut "', b)) or bool(re.search(r'class="soldOut"', b))
        name = re.sub(r"^\[[^\]]*\]\s*", "", raw)
        d = {"name": name, "price": price, "unit": "1kg" if "1kg" in b else "", "soldOut": sold, "cup": notes}
        dh = get(f"{LB}/product/detail.html?product_no={no}")
        DL = text_lines(dh)
        producer = label(DL, ["생산자", "농장주"])
        station = label(DL, ["워싱스테이션", "워싱 스테이션", "마이크로 밀", "마이크로밀", "가공소", "농장"])
        d.update({
            "country": country_of(name), "region": label(DL, "지역"),
            "farm": f"{producer} ({station})" if producer and station else producer or station,
            "variety": label(DL, "품종"), "process": label(DL, "가공방식"), "grade": "",
            "alt": altitude(label(DL, ["재배고도", "고도"])), "harvest": year_of(raw),
            "roast": "", "arrived": label(DL, "입고일자"),
        })
        if not d["cup"]:
            d["cup"] = next((l for l in DL[:80] if l.count(",") >= 2 and not won(l) and len(l) < 80), "")
        items.append(base_item("lb", no, f"{LB}/product/detail.html?product_no={no}&cate_no=57", d,
                               {"isNew": "New Crop" in raw, "tier": None}))
        if n % 20 == 0: print(f"  상세 {n}/{len(blocks)}", file=sys.stderr)
    return items


# ---------------- GSC ----------------
def collect_gsc():
    print("GSC: 생두 목록", file=sys.stderr)
    ids, names, page = [], {}, 1
    while page < 30:
        h = get(f"{GSC}/goods/goods_list.php?cateCd=014&page={page}")
        i = h.find("goods_list_cont"); part = h[i:] if i >= 0 else h
        j = part.find("pagination"); part = part[: j if j > 0 else len(part)]
        got = list(dict.fromkeys(re.findall(r"goods_view\.php\?goodsNo=(\d+)", part)))
        for no, nm in re.findall(r'goods_view\.php\?goodsNo=(\d+)"[^>]*>\s*<img[^>]*alt="([^"]*)"', part):
            names.setdefault(no, html.unescape(nm))
        new = [x for x in got if x not in ids]
        if not new: break
        ids += new; page += 1
    print(f"  {len(ids)}개", file=sys.stderr)
    items = []
    for n, no in enumerate(ids, 1):
        h = get(f"{GSC}/goods/goods_view.php?goodsNo={no}")
        L = text_lines(h)
        m = re.search(r"<title>([^<]+?)\s*-\s*지에스씨", h)
        name = html.unescape(m.group(1)).strip() if m else names.get(no, "")
        opts = re.findall(r'\^\|\^([^"]+?)"', h)
        per = [(o, re.search(r"\(([\d,]+)\s*/\s*kg\)", o)) for o in opts]
        one = next((int(p.group(1).replace(",", "")) for o, p in per if p and o.lower().startswith("1kg")), None)
        unit = "1kg"
        if one is None and per and per[0][1]:  # 1kg 옵션이 없으면 가장 작은 옵션의 kg당 가격(단위 표시)
            one, unit = int(per[0][1].group(1).replace(",", "")), per[0][0].split("(")[0]
        grade = label(L, "구분")
        sold = 'setData("soldOut", "1")' in h
        d = {"name": name, "price": one, "unit": unit, "soldOut": sold,
             "country": country_of(label(L, "원산지"), name), "region": "", "farm": "", "variety": "",
             "process": label(L, "가공방식"), "grade": grade, "alt": None, "harvest": year_of(name),
             "cup": label(L, ["커핑노트", "커핑 노트"]), "roast": "", "harvestSeason": label(L, "수확시기")}
        items.append(base_item("gsc", no, f"{GSC}/goods/goods_view.php?goodsNo={no}", d,
                               {"tier": TIER.get(grade.replace(" ", "")), "sale": "세일" in name or "SALE" in name, "isNew": False}))
        if n % 20 == 0: print(f"  상세 {n}/{len(ids)}", file=sys.stderr)
    return items


def base_item(site, no, url, d, extra):
    it = {"id": f"{site}-{no}", "site": site, "url": url, "name": d.get("name", ""), "price": d.get("price"), "unit": d.get("unit") or "1kg",
          "soldOut": d.get("soldOut", False), "country": d.get("country", ""), "region": d.get("region", ""), "farm": d.get("farm", ""),
          "variety": d.get("variety", ""), "process": d.get("process", ""), "processKey": proc_key((d.get("process") or "") + " " + d.get("name", "")),
          "grade": d.get("grade", ""), "alt": d.get("alt"), "harvest": d.get("harvest"), "cup": d.get("cup", ""), "roast": d.get("roast", "")}
    for k in ("moisture", "densityGL", "scores", "arrived", "harvestSeason"):
        if d.get(k): it[k] = d[k]
    # 이름의 ASD·무산소가 가공 칸보다 우선(앱 파서와 같은 규칙)
    if proc_key(d.get("name", "")) == "무산소": it["processKey"] = "무산소"
    it.update(extra)
    return it


def flavor_taxonomy(groups):
    """생두찾기 향미 항목: 값(한글)과 표시 글의 동의어들."""
    out = []
    for v, lab in groups.get(6, ("", []))[1]:
        words = {v}
        for part in re.split(r"[,/]", lab):
            w = part.strip()
            if w and len(w) > 1: words.add(w)
        for w in v.split("/"): words.add(w.strip())
        out.append({"key": v, "words": sorted(x for x in words if x)})
    return out


def variety_taxonomy(groups):
    out = []
    for v, lab in groups.get(3, ("", []))[1]:
        words = {v} | {w.strip() for w in re.split(r"[,/]", lab) if len(w.strip()) > 1}
        if v == "게이샤": words |= {"게샤", "Gesha"}
        out.append({"key": v, "words": sorted(words)})
    return out


def tag_items(items, flavors, varieties):
    for it in items:
        cup = it.get("cup", "").lower()
        it["flavors"] = [f["key"] for f in flavors if any(w.lower() in cup for w in f["words"])]
        if it["site"] == "sw" and it.get("swTags"):
            vt = it["swTags"].get("품종 및 트랜드 ", it["swTags"].get("품종 및 트랜드", []))
        else:
            txt = (it.get("variety", "") + " " + it["name"]).lower()
            vt = [v["key"] for v in varieties if any(w.lower() in txt for w in v["words"])]
        it["varietyTags"] = vt


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "data/market.json"
    sw, groups = collect_sw()
    lb = collect_lb()
    gs = collect_gsc()
    flavors, varieties = flavor_taxonomy(groups), variety_taxonomy(groups)
    items = sw + lb + gs
    tag_items(items, flavors, varieties)
    kst = datetime.now(timezone(timedelta(hours=9)))
    data = {"updated": kst.strftime("%Y-%m-%d %H:%M"), "sources": SOURCES, "flavors": flavors, "varieties": varieties,
            "swFilters": {g: {"title": t.strip(), "values": [v for v, _ in o]} for g, (t, o) in groups.items() if g != 6},
            "items": [i for i in items if i.get("price")]}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    by = {k: sum(1 for i in data["items"] if i["site"] == k) for k in SOURCES}
    print(f"완료: {out} · {len(data['items'])}개 {by} · 가격 없음 제외 {len(items) - len(data['items'])}개", file=sys.stderr)


if __name__ == "__main__":
    main()
