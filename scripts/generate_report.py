import datetime
import os
import re
import sys

from google import genai
from google.genai import types


REPORT_PROMPT = """\
你是一个专门为心理学研究生搜集实习招聘信息的助手。今天是 {date}。

请通过搜索，查找当前面向心理学研究生开放的企业实习岗位，重点关注：
1. 互联网大厂（腾讯、字节跳动、阿里巴巴、华为、美团、顺丰科技等）的用户研究/UX/产品/HR 方向
2. EAP 服务商（亚太 EAP、中智关爱通、壹心理等）
3. 心理测评 / HR 科技公司（北森、CDP 等）
4. 医疗健康企业（平安健康、丁香园等互联网医疗）
5. 心理咨询平台（简单心理、壹心理等）

筛选原则：
- 企业直招 / 官方校招，剔除付费内推、培训机构
- 优先武汉线下岗位 + 全国远程/线上岗位
- 接受无经验、研一在读学生，不限全日制
- 搜索渠道：实习僧、BOSS 直聘、牛客校招、各公司官网、武汉本地宝

请直接输出完整的 Markdown 报告，不要有任何额外前言：

# 心理学研究生实习招聘日报 {date}

> 汇总统计：共找到**[产品 X 个、用户研究 X 个、HR X 个]**岗位，合计 **X 个**
>
> 搜索渠道：实习僧、BOSS 直聘、牛客校招、小红书校招、智联招聘、武汉本地宝、各公司官网
> 地域范围：武汉线下 + 全国远程/线上
> 筛选原则：企业直招/官方校招，剔除付费内推、培训机构、全职及仅限应届毕业生岗位

---

### 一、产品实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道/链接 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

### 二、用户研究实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道/链接 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

### 三、人力资源/HR 实习生

| 公司名称 | 岗位名称 | 工作地点 | 实习薪资 | 实习时长 | 投递渠道/链接 | 心理学适配度 | 备注 |
|------|------|------|------|------|------|------|------|

---

## 投递建议

| 优先级 | 岗位类型 | 推荐公司 | 理由 |
|------|------|------|------|
| ⭐⭐⭐ | 用户研究实习生 | ... | ... |

## 今日数据说明

- 薪资信息部分来自公开求职社区及新闻，实际以录用后沟通为准
- 各公司招聘周期不同，建议尽快投递，部分岗位招满即止

## 数据来源

- [来源名称](链接)
"""


def generate_report(date_str: str) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=REPORT_PROMPT.format(date=date_str),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )

    result = response.text
    if not result or not result.strip():
        raise ValueError("Generated report is empty")

    return result.strip()


def count_jobs(report_content: str) -> str:
    match = re.search(r"合计\s+\*\*(\d+)\s*个\*\*", report_content)
    if match:
        return match.group(1)
    return "?"


def update_readme(date_str: str, job_count: str):
    readme_path = "README.md"
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_row = f"| {date_str} | [心理学研究生实习招聘日报 {date_str}](./reports/{date_str}.md) | {job_count} 个 |"
    separator = "|------|----------|--------|"

    if separator in content and new_row not in content:
        content = content.replace(
            separator + "\n",
            separator + "\n" + new_row + "\n",
            1,
        )
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    report_path = f"reports/{date_str}.md"

    if os.path.exists(report_path):
        print(f"Report for {date_str} already exists, skipping.")
        return

    print(f"Generating report for {date_str}...")
    try:
        report_content = generate_report(date_str)
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Report saved to {report_path}")

    job_count = count_jobs(report_content)
    update_readme(date_str, job_count)
    print(f"README.md updated (jobs: {job_count})")


if __name__ == "__main__":
    main()
