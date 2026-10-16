"""YouTube Data API(무료 키)로 조회수를 가져온다 — GitHub 워크플로(yt_views)에서만 실행.
입력 stats/request.json: {"queries": ["검색어", ...], "channel": "UC...", "videoIds": ["...", ...]}
출력 stats/result.json: 검색어별 최근 30일 영상(제목·채널·조회수·날짜), 우리 채널 통계, 영상별 통계.
키는 환경변수 YOUTUBE_API_KEY로만 받고 어디에도 출력하지 않는다. 사용량: 검색 1회 약 100단위."""
import datetime as dt, json, os, sys, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3/"
KEY = os.environ.get("YOUTUBE_API_KEY", "")


def get(path, **params):
    params["key"] = KEY
    url = API + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # 키가 담긴 주소는 남기지 않고 상태 코드만
        raise RuntimeError(f"{path} HTTP {e.code}") from None


def video_stats(ids):
    out = {}
    for i in range(0, len(ids), 50):
        r = get("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))
        for v in r.get("items", []):
            s = v.get("statistics", {})
            out[v["id"]] = {"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
                            "publishedAt": v["snippet"]["publishedAt"], "views": int(s.get("viewCount", 0)),
                            "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))}
    return out


def main(req_path, out_path):
    req = json.load(open(req_path, encoding="utf-8"))
    res = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "errors": []}
    if not KEY:
        res["errors"].append("YOUTUBE_API_KEY 없음")
    else:
        after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        res["search"] = {}
        for q in req.get("queries", [])[:5]:
            try:
                r = get("search", part="id", q=q, type="video", regionCode="KR", relevanceLanguage="ko",
                        publishedAfter=after, maxResults=10, order="viewCount")
                ids = [i["id"]["videoId"] for i in r.get("items", [])]
                res["search"][q] = sorted(video_stats(ids).values(), key=lambda v: -v["views"])
            except Exception as e:
                res["errors"].append(f"search {q}: {e}")
        if req.get("channel"):
            try:
                r = get("channels", part="statistics", id=req["channel"])
                s = r["items"][0]["statistics"] if r.get("items") else {}
                res["channel"] = {"subs": int(s.get("subscriberCount", 0)), "views": int(s.get("viewCount", 0)),
                                  "videos": int(s.get("videoCount", 0))}
            except Exception as e:
                res["errors"].append(f"channel: {e}")
        if req.get("videoIds"):
            try:
                res["videos"] = video_stats(req["videoIds"])
            except Exception as e:
                res["errors"].append(f"videos: {e}")
    json.dump(res, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("yt_views:", "오류 " + "; ".join(res["errors"]) if res["errors"] else "완료")


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) > 2 else ("stats/request.json", "stats/result.json")))
