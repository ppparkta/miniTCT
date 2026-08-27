#!/usr/bin/env python3
"""유튜브 채널의 영상 목록으로 data.json의 sessions를 채운다.

API 키가 필요 없다. 채널 RSS 피드만 읽는다.
영상이 15개를 넘으면 RSS로는 최신 15개까지만 나온다. 그 경우
yt-dlp가 설치되어 있으면 자동으로 그쪽을 써서 전체를 가져온다.

    python3 tools/sync_youtube.py                  # 미리보기만
    python3 tools/sync_youtube.py --write          # data.json에 반영

기존에 적어둔 presenter는 영상 ID로 대조해 그대로 유지한다.
새로 들어온 영상의 presenter는 --presenter 로 지정한 이름이 들어간다.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCXXrtSvIWJ2p6RJ1kt9ywvw"          # @soo-yang-1
RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data.json")
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def from_rss(channel_id):
    """RSS 피드에서 (영상ID, 제목, 날짜)를 오래된 것부터 반환. 최신 15개 제한."""
    req = urllib.request.Request(
        RSS.format(channel_id),
        headers={"User-Agent": "Mozilla/5.0 (study-orrery sync)"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        title = (e.findtext("a:title", namespaces=NS) or "").strip()
        published = (e.findtext("a:published", namespaces=NS) or "")[:10]
        if vid:
            out.append({"youtube": vid, "title": title, "date": published})
    return out


def from_ytdlp(channel_id):
    """yt-dlp가 있으면 전체 목록을 가져온다."""
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--ignore-errors", url]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0 and not p.stdout.strip():
        raise RuntimeError(p.stderr.strip()[:300] or "yt-dlp 실행 실패")
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        v = json.loads(line)
        ts = v.get("timestamp") or v.get("release_timestamp")
        if ts:
            import datetime
            date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        else:
            date = (v.get("upload_date") or "")
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else ""
        out.append({"youtube": v["id"], "title": (v.get("title") or "").strip(), "date": date})
    return out


def oldest_first(vids):
    """오래된 회차가 안쪽 궤도가 되도록 정렬한다.
    RSS와 yt-dlp 모두 최신순으로 주지만, 순서 가정에 기대지 않고 날짜로 정렬한다.
    날짜가 없는 항목은 원래 순서를 뒤집어 뒤에 붙인다."""
    dated = [v for v in vids if v.get("date")]
    undated = [v for v in vids if not v.get("date")]
    dated.sort(key=lambda v: v["date"])
    undated.reverse()
    return dated + undated


def clean_title(t):
    """제목 앞에 붙은 [n회차], #3 같은 표기를 떼어 본문만 남긴다."""
    t = re.sub(r"^\s*[\[\(]?\s*(?:제\s*)?\d+\s*(?:회차|회|화)\s*[\]\)]?\s*[-–—:.]?\s*", "", t)
    t = re.sub(r"^\s*#\d+\s*[-–—:.]?\s*", "", t)
    t = re.sub(r"\s*\|\s*미니테코톡\s*$", "", t)
    return t.strip() or "제목 없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default=CHANNEL_ID, help="채널 ID (UC로 시작)")
    ap.add_argument("--presenter", default="미정", help="새 영상에 넣을 발표자 이름")
    ap.add_argument("--write", action="store_true", help="data.json에 실제로 반영")
    ap.add_argument("--keep-titles", action="store_true",
                    help="이미 적어둔 제목을 유튜브 제목으로 덮어쓰지 않음")
    args = ap.parse_args()

    if shutil.which("yt-dlp"):
        print("yt-dlp 사용 (전체 목록)")
        try:
            vids = from_ytdlp(args.channel)
        except Exception as e:
            print(f"  실패, RSS로 대체: {e}")
            vids = from_rss(args.channel)
    else:
        print("RSS 사용 (최신 15개까지). 영상이 더 많으면 pip install yt-dlp 후 다시 실행")
        vids = from_rss(args.channel)

    if not vids:
        sys.exit("영상을 찾지 못했습니다. 채널 ID를 확인해주세요.")

    vids = oldest_first(vids)

    data = json.load(open(DATA, encoding="utf-8"))
    old_by_id = {s.get("youtube"): s for s in data["sessions"] if s.get("youtube")}
    old_by_no = {s["no"]: s for s in data["sessions"]}

    sessions = []
    for i, v in enumerate(vids, start=1):
        prev = old_by_id.get(v["youtube"]) or old_by_no.get(i, {})
        title = prev.get("title") if (args.keep_titles and prev.get("title")) else clean_title(v["title"])
        sessions.append({
            "no": i,
            "date": v["date"] or prev.get("date", ""),
            "title": title,
            "presenter": prev.get("presenter", args.presenter),
            "youtube": v["youtube"],
        })

    print(f"\n영상 {len(sessions)}개")
    known = set(data.get("crew", {}))
    for s in sessions:
        flag = "" if s["presenter"] in known else "  <- crew에 없는 이름"
        print(f"  {s['no']:2d}회차  {s['date']}  {s['youtube']}  {s['presenter']}{flag}")
        print(f"          {s['title']}")

    missing = {s["presenter"] for s in sessions if s["presenter"] not in known}
    if missing:
        print(f"\ncrew에 등록되지 않은 이름: {', '.join(sorted(missing))}")
        print("data.json의 crew에 추가하지 않으면 회색 구체로 표시됩니다.")

    if not args.write:
        print("\n미리보기입니다. 반영하려면 --write 를 붙여 다시 실행하세요.")
        return

    shutil.copyfile(DATA, DATA + ".bak")
    data["sessions"] = sessions
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\ndata.json 갱신 완료 (이전 파일은 data.json.bak)")
    print("발표자 이름을 확인하고 필요하면 직접 고쳐주세요.")


if __name__ == "__main__":
    main()
