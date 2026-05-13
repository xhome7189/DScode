"""
抓取观察者网 (https://www.guancha.cn/?s=fwdhguan) 首页信息
"""

import requests
import re
from html import unescape
from datetime import datetime


def fetch_guancha_news():
    """抓取观察者网首页新闻列表"""
    url = "https://www.guancha.cn/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.guancha.cn/",
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "utf-8"

    if resp.status_code != 200:
        print(f"请求失败，状态码: {resp.status_code}")
        return []

    html = resp.text
    news_list = []

    # 方法1: 用正则提取新闻标题和链接
    # 观察者网常见的条目模式
    # <a href="/xxxxx" ...>标题</a> 带 target="_blank" 的一般是新闻
    pattern = r'<a\s+href="(/\d{4}/\d{2}/\d{2/[^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html)

    seen = set()
    for href, title in matches:
        title = title.strip()
        if not title or len(title) < 5:
            continue
        if title in seen:
            continue
        seen.add(title)

        full_url = f"https://www.guancha.cn{href}" if href.startswith("/") else href
        news_list.append({
            "title": unescape(title),
            "url": full_url,
        })

    # 限前30条
    return news_list[:30]


def main():
    print("=" * 60)
    print(f"  观察者网 - 新闻抓取")
    print(f"  抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        news = fetch_guancha_news()
    except Exception as e:
        print(f"\n❌ 抓取失败: {e}")
        return

    if not news:
        print("\n未抓到新闻，可能需要更新正则匹配规则")
        return

    print(f"\n共抓取 {len(news)} 条新闻:\n")

    for i, item in enumerate(news, 1):
        print(f"  {i:2d}. {item['title']}")
        print(f"       {item['url']}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    main()
