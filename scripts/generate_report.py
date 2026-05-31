#!/usr/bin/env python3
"""心理学研究生实习招聘日报 - 真实爬虫版"""
import asyncio
import datetime
import os
import re
import sys

from openai import OpenAI
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


SCRAPE_TARGETS = [
    ("https://www.shixiseng.com/interns?keyword=心理&city=全国", "实习僧-心理", 4000),
    ("https://www.shixiseng.com/interns?keyword=用户研究&city=全国", "实习僧-用户研究", 4000),
    ("https://www.shixiseng.com/interns?keyword=EAP&city=全国", "实习僧-EAP", 3000),
    ("https://www.shixiseng.com/interns?keyword=心理测评&city=全国", "实习僧-心理测评", 3000),
    ("https://sou.zhaopin.com/?jl=&kw=心理实习&kt=3", "智联招聘-心理实习", 4000),
    ("https://sou.zhaopin.com/?jl=&kw=用户研究实习&kt=3", "智联招聘-用户研究", 4000),
    ("https://www.nowcoder.com/jobs?type=2&area=0&keyword=心理", "牛客网-心理", 4000),
]

FORMAT_PROMPT = """\
你是招聘信息整理助手。下面是今天（{date}）从各招聘平台真实爬取的原始文本数据，请按以下规则处理：

【核心原则】
1. 只提取原始数据中真实存在的招聘岗位，绝对不能编造或补全任何公司/岗位信息
2. 如果某类别确实没有找到相关岗位，在表格中写"今日暂无此类岗位"
3. 筛选标准：面向在读学生的实习岗位；优先武汉线下 + 全国远程；剔除付费内推、培训机构

【原始爬取数据】
{raw_data}

请整理为以下格式的完整 Markdown 报告，严格按格式输出，不加任何额外前言：

# 心理学研究生实习招聘日报 {date}

> 汇总统计：共找到**[产品 X 个、用户研究 X 个、HR X 个]**岗位，合计 **X 个**
>
> 数据来源：实习僧、智联招聘、牛客网（真实爬取，{date} 更新）
> 地域范围：武汉线下 + 全国远程/线上
> 筛选原则：企业直招/官方校招，剔除付费内推、培训机构

---

### 一、产品实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

### 二、用户研究实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

### 三、人力资源/HR 实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

## 爬取状态说明

（注明各平台爬取是否成功、获取到多少条原始数据）

## 投递建议

| 优先级 | 岗位类型 | 推荐公司 | 理由 |
|------|------|------|------|
| ⭐⭐⭐ | 用户研究实习生 | ... | ... |
| ⭐⭐⭐ | HR实习生 | ... | ... |
| ⭐⭐ | 产品实习生 | ... | ... |

## 数据来源

- [实习僧](https://www.shixiseng.com/)
- [智联招聘](https://sou.zhaopin.com/)
- [牛客网](https://www.nowcoder.com/jobs)
"""


async def scrape_url(browser, url: str, label: str, wait_ms: int) -> str:
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(wait_ms)

        content = await page.content()
        await context.close()

        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "header", "footer", "nav"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) >= 2]

        seen: set[str] = set()
        unique: list[str] = []
        for l in lines:
            if l not in seen:
                seen.add(l)
                unique.append(l)

        snippet = "\n".join(unique[:250])
        return f"\n=== {label} ===\n{snippet}\n"

    except Exception as e:
        print(f"爬取失败 [{label}]: {e}", file=sys.stderr)
        return f"\n=== {label} ===\n爬取失败: {e}\n"


async def gather_all_data() -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        tasks = [
            scrape_url(browser, url, label, wait_ms)
            for url, label, wait_ms in SCRAPE_TARGETS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await browser.close()

    parts = []
    for r in results:
        if isinstance(r, Exception):
            parts.append(f"爬取异常: {r}")
        else:
            parts.append(str(r))
    return "\n".join(parts)


def format_with_ai(raw_data: str, date_str: str) -> str:
    client = OpenAI(
        api_key=os.environ["SILICONFLOW_API_KEY"],
        base_url="https://api.siliconflow.cn/v1",
    )
    prompt = FORMAT_PROMPT.format(date=date_str, raw_data=raw_data[:30000])
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.1,
    )
    result = response.choices[0].message.content
    if not result or not result.strip():
        raise ValueError("AI 返回内容为空")
    return result.strip()


def count_jobs(report_content: str) -> str:
    match = re.search(r"合计\s+\*\*(\d+)\s*个\*\*", report_content)
    if match:
        return match.group(1)
    return "?"


def update_readme(date_str: str, job_count: str) -> None:
    readme_path = "README.md"
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_row = (
        f"| {date_str} | "
        f"[心理学研究生实习招聘日报 {date_str}](./reports/{date_str}.md) | "
        f"{job_count} 个 |"
    )
    separator = "|------|----------|--------|"

    if separator in content and new_row not in content:
        content = content.replace(
            separator + "\n",
            separator + "\n" + new_row + "\n",
            1,
        )
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)


def main() -> None:
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    report_path = f"reports/{date_str}.md"

    if os.path.exists(report_path):
        print(f"今日报告已存在: {report_path}，跳过。")
        return

    print("开始爬取各平台数据...")
    raw_data = asyncio.run(gather_all_data())
    print(f"爬取完成，共获取 {len(raw_data)} 字符")

    print("调用 AI 格式化报告...")
    try:
        report_content = format_with_ai(raw_data, date_str)
    except Exception as e:
        print(f"AI 格式化失败: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"报告已保存: {report_path}")

    job_count = count_jobs(report_content)
    update_readme(date_str, job_count)
    print(f"README 已更新（岗位数: {job_count}）")


if __name__ == "__main__":
    main()
