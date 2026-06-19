#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import textwrap
import urllib.parse
from html import escape
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

MCP_URL = "https://changfengbox.top/api/mcp"
TIMEOUT = 120
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR_1 = SKILL_DIR / "assets" / "template1"
TEMPLATE_DIR_2 = SKILL_DIR / "assets" / "template2"
TEMPLATE_DIR_3 = SKILL_DIR / "assets" / "template3"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "wechat-monitor" / "output"
USP_SEPARATOR = "·"
TAIL_IMAGE_BOUNDARY_FRAGMENTS = [
    "O4S31l7wCFJqWpeLPjziaibleMm4WF2WPjUSIN3yXNyMsdrTQFuxEy7mDpNJVLtAcXRnJicc1wJlXHd21XLrr0E1RUnPsCfV8KNwtuPYqmiaBnA",
]
TAIL_TEXT_MARKERS = [
    "在线就诊指南",
    "近期热文",
    "有爱不惧癌",
    "点击上方告诉我们您的抗癌故事",
    "点击专家名片预约门诊",
    "喜欢此内容的人还喜欢",
]
TAIL_PREFIX_PATTERNS = [
    r"^撰文[:：]",
    r"^编辑[:：]",
    r"^责编[:：]",
    r"^审核[:：]",
    r"^来源[:：]",
]
SECTION_HEADING_PATTERNS = [
    r"^.+[？?]$",
    r"^什么是.+",
    r"^哪些.+",
    r"^为什么.+",
    r"^如何.+",
    r"^第[一二三四五六七八九十]+[部分章节]",
    r"^[一二三四五六七八九十]+[、.．]\s*.+",
]

TEMPLATES = {
    ("template1", "morandi_purple"): TEMPLATE_DIR_1 / "xyb_template_morandi_purple.html",
    ("template1", "morandi_green"): TEMPLATE_DIR_1 / "xyb_template_morandi_green.html",
    ("template2", "morandi_purple"): TEMPLATE_DIR_2 / "xyb2_template_morandi_purple.html",
    ("template2", "morandi_green"): TEMPLATE_DIR_2 / "xyb2_template_morandi_green.html",
    ("template3", "raw_original"): TEMPLATE_DIR_3 / "xyb3_template_raw_original.html",
}

COLOR_META = {
    "template1": {
        "morandi_purple": {"main": "#5c4a7a", "accent": "#7a5080", "bg": "#f3f0f8"},
        "morandi_green": {"main": "#4a6a5a", "accent": "#6a8a7a", "bg": "#f0f5f2"},
    },
    "template2": {
        "morandi_purple": {"main": "#5c4a7a", "accent": "#7a5080", "bg": "#f3f0f8"},
        "morandi_green": {"main": "#4a6a5a", "accent": "#6a8a7a", "bg": "#f0f5f2"},
    },
    "template3": {
        "raw_original": {"main": "#5c4a7a", "accent": "#7a5080", "bg": "#f3f0f8"},
    },
}

DEFAULT_FOOTER = textwrap.dedent(
    """
    <section style="display:flex;align-items:center;margin:28px 30px 15px;">
      <span style="display:inline-block;width:4px;height:20px;background-color:__MAIN__;border-radius:2px;margin-right:10px;"></span>
      <strong style="font-size:16px;color:__MAIN__;">关于小胰宝</strong>
    </section>

    <section style="font-family:'PingFangSC-light','PingFang SC',sans-serif;font-size:13px;padding:0 20px;letter-spacing:1px;line-height:1.9;text-align:justify;margin:15px 0;">
      <p style="margin:0 0 10px;"><strong style="color:__MAIN__;">小胰宝</strong>是一个面向胰腺肿瘤患者及家属的开源公益项目，归属<strong>小X宝社区</strong>和<strong>天工开物基金会</strong>管理。通过社区2025蓝马甲志愿者行动，以及AI工具/应用矩阵，小胰宝以"AI+人文"方式，全心全意推动肿瘤/罕见病患者信息效率改善和关怀。</p>
      <p style="margin:0 0 10px;"><strong style="color:__MAIN__;">小X宝社区</strong>（info.xiao-x-bao.com.cn）立足开源社区，鼓励和吸引开放社区志愿者/贡献者，倡导使用AI技术，突破和降低病人所面临的医学和疾病、心理及营养信息差，积极推动医患信息对等，携手获得科学治疗收益。</p>
      <p style="margin:0;">小X宝社区志愿者们完成公益贡献<strong>8个癌种+1个罕见病</strong>的AI助手，欢迎有共同价值观的公益病友群发起人联系，推动40+癌种/200+罕见病/慢性病患者应用早日普及。</p>
    </section>

    <section style="text-align:center;margin:15px 30px 10px;font-size:12px;color:#8d949f;line-height:2;">
      <p style="font-size:13px;color:__MAIN__;font-weight:600;margin-bottom:6px;">关注我们</p>
      <p style="margin:0;">小红书 @小胰宝宝 ｜ 公众号 @小胰宝助手</p>
      <p style="margin:0;">播客·小宇宙 @微光成炬 胰路同心</p>
      <p style="margin:0;">官网：www.xiaoyibao.com.cn</p>
    </section>

    <section style="margin:30px 20px 20px;background:#fff;border-radius:16px;padding:40px 30px;text-align:center;">
      <p style="font-size:42px;margin-bottom:25px;">🌿🍃</p>
      <p style="font-size:14px;color:#3e3e3e;line-height:2.2;font-weight:300;font-family:'PingFangSC-light','PingFang SC',sans-serif;letter-spacing:2px;margin:0;">愿每一份前沿信息，</p>
      <p style="font-size:14px;color:#3e3e3e;line-height:2.2;font-weight:300;font-family:'PingFangSC-light','PingFang SC',sans-serif;letter-spacing:2px;margin:0;">都能为你带来一点光亮与希望。</p>
      <p style="height:25px;margin:0;"></p>
      <p style="font-size:13px;color:#666;line-height:2;font-weight:300;font-family:'PingFangSC-light','PingFang SC',sans-serif;letter-spacing:2px;margin:0;">With love and hope,</p>
      <p style="font-size:13px;color:#666;line-height:2;font-weight:300;font-family:'PingFangSC-light','PingFang SC',sans-serif;letter-spacing:2px;margin:0;">小胰宝志愿者团队</p>
      <p style="font-size:13px;color:#666;line-height:2;font-weight:300;font-family:'PingFangSC-light','PingFang SC',sans-serif;letter-spacing:2px;margin:0;">AI+人文 · 胰路同心</p>
    </section>

    <section style="text-align:center;padding:15px 30px 30px;font-size:11px;color:#aaa;line-height:1.6;">
      <p style="margin:0;">本文仅供科普参考，不构成医疗建议或投资建议。</p>
      <p style="margin:0;">参考文献：请在此处列出引用来源</p>
    </section>
    """
)


def call_mcp(tool_name: str, arguments: Dict) -> Dict:
    payload = {"jsonrpc": "2.0", "method": "tools/call", "id": 1, "params": {"name": tool_name, "arguments": arguments}}
    resp = requests.post(MCP_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def build_config(formats=("html", "md")) -> Dict:
    mapping = {"html": "HTML", "md": "MD", "pdf": "PDF", "word": "WORD", "docx": "WORD", "txt": "TXT", "mhtml": "MHTML"}
    config = {"保存离线网页": True, "文件开头添加日期": True, "HTML": False, "MD": False, "PDF": False, "WORD": False, "TXT": False, "MHTML": False}
    for fmt in formats:
        key = mapping.get(fmt.lower())
        if key:
            config[key] = True
    if not any(config[k] for k in ("HTML", "MD", "PDF", "WORD", "TXT", "MHTML")):
        config["HTML"] = True
        config["MD"] = True
    return config


def download_article(url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = call_mcp("wechat", {"url": url, "config": build_config()})
    items = result.get("result", {}).get("content", [])
    for item in items:
        try:
            data = json.loads(item.get("text", "{}"))
        except Exception:
            continue
        for remote_url in data.get("urls", []):
            content = requests.get(remote_url, timeout=30)
            content.raise_for_status()
            title = Path(urllib.parse.unquote(remote_url.split("?")[0])).stem or "wechat_article"
            out = output_dir / f"{title}.html"
            out.write_bytes(content.content)
            return out
    raise RuntimeError("failed to download article via MCP")


def read_source(path: Path) -> Tuple[str, str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".html", ".htm"}:
        title = find_title(raw) or clean_generated_title(path.stem)
        body = extract_wechat_body_html(raw)
        if not body.strip():
            body = html_to_text(raw)
    else:
        title = clean_generated_title(path.stem)
        body = raw
    return title, body


def get_template_mode(family: str, style: str) -> str:
    if family == "template3":
        return "raw_original"
    return style


def find_title(raw_html: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:title["\']',
        r'<title[^>]*>(.*?)</title>',
        r'class=["\']rich_media_title["\'][^>]*>(.*?)</',
    ]
    for pattern in patterns:
        m = re.search(pattern, raw_html, re.I | re.S)
        if m:
            return clean_generated_title(clean_text(m.group(1)))
    return None


def extract_wechat_body_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    root = soup.find(id="js_content")
    if root is None:
        return ""
    return "".join(str(child) for child in root.children)


def html_to_text(raw_html: str) -> str:
    raw_html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", raw_html)
    raw_html = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    raw_html = re.sub(r"(?i)</p\s*>", "\n\n", raw_html)
    raw_html = re.sub(r"(?i)</section\s*>", "\n", raw_html)
    raw_html = re.sub(r"(?i)<img\b[^>]*>", "\n[图片]\n", raw_html)
    return clean_text(raw_html)


def clean_text(text: str) -> str:
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(body: str) -> List[str]:
    parts = [normalize_paragraph(p) for p in re.split(r"\n\s*\n", body)]
    parts = [p for p in parts if p]
    if not parts and body.strip():
        parts = [normalize_paragraph(line) for line in body.splitlines()]
        parts = [p for p in parts if p]
    return parts


def make_summary(paragraphs: List[str]) -> str:
    if not paragraphs:
        return "未抽取到正文内容。"
    headline = paragraphs[0]
    second = paragraphs[1] if len(paragraphs) > 1 else ""
    third = paragraphs[2] if len(paragraphs) > 2 else ""
    items = [headline]
    for item in (second, third):
        if item:
            items.append(item)
    return " ".join(items)[:96]


def make_usp(title: str, summary: str) -> str:
    def split_chunks(source: str) -> List[str]:
        parts = re.split(r"[：:，。！？!?,\s]+", source)
        return [normalize_paragraph(p) for p in parts if normalize_paragraph(p)]

    def to_four(text: str) -> str:
        text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
        if len(text) >= 4:
            return text[:4]
        return text.ljust(4, text[-1] if text else "光")

    def four_phrase(*parts: str, default: str) -> str:
        raw = "".join(parts)
        raw = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", raw)
        if len(raw) >= 4:
            return raw[:4]
        return to_four(default)

    def has_any(source: str, words: List[str]) -> bool:
        return any(word in source for word in words)

    title_chunks = split_chunks(title)
    summary_chunks = split_chunks(summary)
    source = f"{title} {summary}"

    conflict_pairs = [
        (
            ["贵药", "高价药", "昂贵药", "用贵药", "不敢用", "难用", "不用"],
            ["背锅", "担责", "责任", "审计", "问责", "风险", "解释"],
            ("贵药难用", "责任难担"),
        ),
        (
            ["患者", "关怀", "陪伴", "照护", "呵护"],
            ["AI", "向善", "善意", "温暖", "帮助"],
            ("AI向善", "患者关怀"),
        ),
        (
            ["光已成炬", "照亮", "崎岖", "黑客松", "开源", "共创"],
            ["医疗", "社区", "公益", "实践", "行动"],
            ("光已成炬", "照亮崎岖"),
        ),
    ]

    left = ""
    right = ""

    for left_words, right_words, fallback_pair in conflict_pairs:
        if has_any(source, left_words) and has_any(source, right_words):
            if not left:
                for word in left_words:
                    if word in source:
                        left = four_phrase(word, default=fallback_pair[0])
                        break
            if not right:
                for word in right_words:
                    if word in source:
                        right = four_phrase(word, default=fallback_pair[1])
                        if right != left:
                            break
            if left and right and left != right:
                return f"{left}{USP_SEPARATOR}{right}"

    if not left:
        for chunk in title_chunks + summary_chunks:
            if len(re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", chunk)) >= 4:
                left = to_four(chunk)
                break

    if not right:
        if has_any(source, ["不敢用", "难用", "怕的是", "背锅", "责任", "问责"]):
            right = four_phrase("责任", "难担", default="责任难担")
        elif has_any(source, ["贵药", "高价药", "昂贵药", "用药", "药贵"]):
            right = four_phrase("背锅", "难扛", default="背锅难扛")
        elif has_any(source, ["患者", "关怀", "照护", "温暖"]):
            right = four_phrase("患者", "关怀", default="患者关怀")
        elif has_any(source, ["AI", "向善", "公益", "善意"]):
            right = four_phrase("AI向", "善", default="AI向善")
        if not right:
            for chunk in title_chunks + summary_chunks:
                normalized = to_four(chunk)
                if normalized != left:
                    right = normalized
                    break

    if not left:
        left = "医疗共创"
    if not right:
        right = "真实场景"

    return f"{left}{USP_SEPARATOR}{right}"


def clean_raw_original_html(raw_html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    root = soup.find(id="js_content")
    if root is None:
        return "", ""
    clean_wechat_dom(root)
    summary_parts: List[str] = []
    for node in root.find_all(True):
        if len(summary_parts) >= 3:
            break
        text = normalize_paragraph(node.get_text(" ", strip=True))
        if text:
            summary_parts.append(text)
    return str(root), " ".join(summary_parts)[:220]


def rewrite_article(title: str, body: str, rewrite_req: str, mode: str = "preset") -> Dict[str, str]:
    if "<" in body and ">" in body:
        if mode == "raw_original":
            intro_html, body_html, summary = sanitize_wechat_html(body)
        else:
            intro_html, body_html, summary = restructure_wechat_html(body)
        return {"intro": intro_html, "body": body_html, "summary": summary}

    paragraphs = split_paragraphs(body)
    summary = make_summary(paragraphs)
    intro_html = "\n".join(f'<p style="margin:0 0 10px;">{escape(p)}</p>' for p in paragraphs[:3])
    body_html = "\n".join(render_paragraph(p) for p in paragraphs[3:])
    return {"intro": intro_html, "body": body_html, "summary": summary}


def restructure_wechat_html(raw_html: str) -> Tuple[str, str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    blocks: List[str] = []
    summary_parts: List[str] = []

    for node in soup.children:
        if isinstance(node, NavigableString):
            continue
        if not isinstance(node, Tag):
            continue
        rendered, plain, should_stop = render_node(node, "__MAIN__", trim_leading_media=True)
        if not rendered:
            if should_stop:
                break
            continue
        if len(summary_parts) < 3 and plain:
            summary_parts.append(plain)
        blocks.append(rendered)
        if should_stop:
            break

    blocks = drop_leading_media_blocks(blocks)
    blocks = [block for block in blocks if not is_empty_html_block(block)]
    intro = "\n".join(blocks[:4])
    body = "\n".join(blocks[4:])
    summary = " ".join(summary_parts)[:220]
    return intro, body, summary


def render_paragraph(paragraph: str) -> str:
    text = paragraph.strip()
    if not text:
        return ""
    if text.startswith(("•", "-", "—")):
        return f'<p style="margin:0 0 10px;">{escape(text)}</p>'
    return f'<p style="margin:0 0 10px;">{escape(text)}</p>'


def sanitize_wechat_html(raw_html: str) -> Tuple[str, str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    root = soup
    truncate_tail(root)
    clean_wechat_dom(root)
    blocks, summary_parts = collect_clean_blocks(root)
    blocks = drop_leading_media_blocks(blocks)
    blocks = [block for block in blocks if not is_empty_html_block(block)]
    intro = "\n".join(blocks[:4])
    body = "\n".join(blocks[4:])
    summary = " ".join(summary_parts)[:220]
    return intro, body, summary


def clean_wechat_dom(root: Tag) -> None:
    truncate_tail(root)
    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag) or not getattr(tag, "name", None):
            continue
        if should_drop_tag(tag):
            tag.decompose()
            continue
        clean_tag_attrs(tag)


def should_drop_tag(tag: Tag) -> bool:
    name = tag.name.lower()
    if name in {"script", "style", "iframe", "mp-style-type"}:
        return True

    if tag.get("aria-hidden") == "true":
        return True

    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style:
        return True

    classes = " ".join(tag.get("class", [])).lower()
    drop_class_keywords = [
        "wx_profile_card",
        "js_uneditable",
        "original_primary_card",
        "reward_area",
        "js_product_container",
        "js_topic_tag",
        "js_improve_read",
        "wxw-img_loading",
    ]
    if any(keyword in classes for keyword in drop_class_keywords):
        return True

    text = normalize_paragraph(tag.get_text(" ", strip=True))
    if not text:
        return False

    noise_patterns = [
        r"^微信扫一扫",
        r"^继续滑动看下一个",
        r"^轻触阅读原文$",
        r"^阅读原文$",
        r"^喜欢此内容的人还喜欢$",
        r"^人划线$",
        r"^分享收藏点赞在看$",
        r"^本文转载自",
    ]
    return any(re.search(pattern, text) for pattern in noise_patterns)


def truncate_tail(root: Tag) -> None:
    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag) or not getattr(tag, "name", None):
            continue
        if is_tail_boundary(tag):
            remove_from_boundary(tag)
            break


def is_tail_boundary(tag: Tag) -> bool:
    if is_tail_boundary_image(tag):
        return True
    text = normalize_paragraph(tag.get_text(" ", strip=True))
    if not text:
        return False
    compact = re.sub(r"\s+", "", text)
    if len(compact) > 40:
        return False
    if compact in TAIL_TEXT_MARKERS:
        return True
    if any(marker in compact for marker in TAIL_TEXT_MARKERS) and len(compact) <= 30:
        return True
    return any(re.search(pattern, compact) for pattern in TAIL_PREFIX_PATTERNS)


def is_tail_boundary_image(tag: Tag) -> bool:
    images = [tag] if tag.name and tag.name.lower() == "img" else list(tag.find_all("img"))
    for img in images:
        src = first_non_empty_attr(img, ["src", "data-src", "data-original", "data-actualsrc", "data-backsrc"])
        if any(fragment in src for fragment in TAIL_IMAGE_BOUNDARY_FRAGMENTS):
            if tag is img:
                return True
            text = normalize_paragraph(tag.get_text(" ", strip=True))
            return not text
    return False


def remove_from_boundary(tag: Tag) -> None:
    boundary = find_removable_boundary(tag)
    for sibling in list(boundary.find_next_siblings()):
        sibling.decompose()
    boundary.decompose()


def find_removable_boundary(tag: Tag) -> Tag:
    current = tag
    while isinstance(current.parent, Tag):
        parent = current.parent
        if parent.name and parent.name.lower() in {"[document]", "body", "html"}:
            break
        if parent.find_previous_sibling() or parent.find_next_sibling():
            current = parent
            continue
        break
    return current


def clean_tag_attrs(tag: Tag) -> None:
    allowed = {"href", "src", "data-src", "data-original", "data-actualsrc", "data-backsrc", "style", "colspan", "rowspan"}
    for attr in list(tag.attrs):
        if attr.lower().startswith("on"):
            del tag.attrs[attr]
            continue
        if attr not in allowed:
            del tag.attrs[attr]

    if tag.name.lower() == "img":
        src = first_non_empty_attr(tag, ["src", "data-src", "data-original", "data-actualsrc", "data-backsrc"])
        tag.attrs = {"src": src, "style": "width:100%;border-radius:8px;"} if src else {}
    elif tag.name.lower() == "a":
        href = tag.get("href", "").strip()
        if href.startswith("javascript:"):
            tag.attrs.pop("href", None)


def collect_clean_blocks(root: Tag) -> Tuple[List[str], List[str]]:
    blocks: List[str] = []
    summary_parts: List[str] = []

    for node in root.children:
        if isinstance(node, NavigableString):
            continue
        if not isinstance(node, Tag):
            continue
        html = str(node).strip()
        plain = normalize_paragraph(node.get_text(" ", strip=True))
        if not html:
            continue
        blocks.append(html)
        if len(summary_parts) < 3 and plain:
            summary_parts.append(plain)

    return blocks, summary_parts


def drop_leading_media_blocks(blocks: List[str]) -> List[str]:
    trimmed = list(blocks)
    while trimmed and is_media_only_html(trimmed[0]):
        trimmed.pop(0)
    return trimmed


def is_media_only_html(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_paragraph(soup.get_text(" ", strip=True))
    if text:
        return False
    return bool(soup.find("img"))


def is_empty_html_block(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_paragraph(soup.get_text(" ", strip=True))
    return not text and not soup.find("img") and not soup.find("table")


def trim_leading_media_fragment(html: str) -> str:
    soup = BeautifulSoup(f"<root>{html}</root>", "html.parser")
    root = soup.find("root")
    if not root:
        return html
    trim_leading_media_nodes(root)
    return "".join(str(child) for child in root.children).strip()


def trim_leading_media_nodes(container: Tag) -> None:
    for child in list(container.children):
        if isinstance(child, NavigableString):
            if normalize_paragraph(str(child)):
                return
            child.extract()
            continue
        if not isinstance(child, Tag):
            continue
        if is_empty_tag(child) or is_media_only_tag(child):
            child.decompose()
            continue
        if not direct_text(child):
            trim_leading_media_nodes(child)
            if is_empty_tag(child) or is_media_only_tag(child):
                child.decompose()
                continue
        return


def is_empty_tag(tag: Tag) -> bool:
    text = normalize_paragraph(tag.get_text(" ", strip=True))
    return not text and not tag.find("img") and not tag.find("table")


def is_media_only_tag(tag: Tag) -> bool:
    text = normalize_paragraph(tag.get_text(" ", strip=True))
    return not text and bool(tag.find("img")) and not tag.find("table")


def direct_text(tag: Tag) -> str:
    parts = [str(child) for child in tag.children if isinstance(child, NavigableString)]
    return normalize_paragraph(" ".join(parts))


def render_node(node: Tag, main_color: str = "__MAIN__", trim_leading_media: bool = False) -> Tuple[str, str, bool]:
    name = node.name.lower()
    plain = normalize_paragraph(node.get_text(" ", strip=True))

    if is_tail_boundary(node):
        return "", "", True

    if name in {"h1", "h2", "h3"} or is_section_heading(node, plain):
        if not plain:
            return "", "", False
        return render_module_heading(plain, main_color), plain, False

    if name == "p":
        if not plain:
            return "", "", False
        return f'<p style="margin:0 0 10px;">{render_inline(node)}</p>', plain, False

    if name in {"figure", "img"}:
        img = node if name == "img" else node.find("img")
        if not img:
            return "", "", False
        src = first_non_empty_attr(
            img,
            [
                "src",
                "data-src",
                "data-original",
                "data-actualsrc",
                "data-backsrc",
            ],
        )
        if not src:
            return "", "", False
        html = (
            '<section style="text-align:center;margin:20px 20px 15px;">'
            f'<img src="{escape(src, quote=True)}" alt="" style="width:100%;border-radius:8px;">'
            '</section>'
        )
        return html, "", False

    if name == "table":
        return render_table(node), plain, False

    if name in {"section", "div"}:
        rendered_children = []
        child_texts = []
        should_stop = False
        for child in node.children:
            if isinstance(child, NavigableString):
                continue
            if not isinstance(child, Tag):
                continue
            child_html, child_plain, child_stop = render_node(child, main_color)
            if child_html:
                rendered_children.append(child_html)
            if child_plain:
                child_texts.append(child_plain)
            if child_stop:
                should_stop = True
                break
        rendered_children = [part for part in rendered_children if not is_empty_html_block(part)]
        if trim_leading_media:
            rendered_children = drop_leading_media_blocks(rendered_children)
        rendered_html = "\n".join(part for part in rendered_children if part).strip()
        if trim_leading_media and rendered_html:
            rendered_html = trim_leading_media_fragment(rendered_html)
        child_text = " ".join(part for part in child_texts if part).strip()
        if rendered_html:
            return rendered_html, child_text, should_stop
        if plain:
            return "", plain, should_stop
        return "", "", should_stop

    return "", plain, False


def is_section_heading(node: Tag, plain: str) -> bool:
    if not plain:
        return False
    if len(plain) > 34:
        return False
    if node.name.lower() not in {"p", "section", "div"}:
        return False
    if node.find("img") or node.find("table"):
        return False
    if node.name.lower() in {"section", "div"} and len([child for child in node.find_all(["p", "section", "div"], recursive=False)]) > 1:
        return False
    if node.find(["strong", "b"]):
        return True
    return any(re.search(pattern, plain) for pattern in SECTION_HEADING_PATTERNS)


def render_module_heading(text: str, main_color: str) -> str:
    return (
        '<section style="display:flex;align-items:center;margin:28px 30px 15px;">'
        f'<span style="display:inline-block;width:4px;height:20px;background-color:{main_color};border-radius:2px;margin-right:10px;"></span>'
        f'<strong style="font-size:16px;color:{main_color};">{escape(text)}</strong>'
        '</section>'
    )


def first_non_empty_attr(node: Tag, attr_names: List[str]) -> str:
    for attr_name in attr_names:
        value = node.get(attr_name, "")
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
    return ""


def render_inline(node: Tag) -> str:
    parts: List[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(escape(text))
            continue
        if not isinstance(child, Tag):
            continue
        if child.name.lower() in {"strong", "b"}:
            text = normalize_paragraph(child.get_text(" ", strip=True))
            if text:
                parts.append(f'<strong style="color:__MAIN__;">{escape(text)}</strong>')
        elif child.name.lower() == "br":
            parts.append("<br>")
        else:
            text = normalize_paragraph(child.get_text(" ", strip=True))
            if text:
                parts.append(escape(text))
    joined = " ".join(part for part in parts if part)
    return re.sub(r"\s+<br>\s+", "<br>", joined).strip()


def render_table(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        header = bool(tr.find("th"))
        for cell in tr.find_all(["th", "td"]):
            text = normalize_paragraph(cell.get_text(" ", strip=True))
            tag = "th" if header or cell.name.lower() == "th" else "td"
            style = (
                "padding:10px 12px;border:1px solid #d8cfe7;text-align:left;background:#efe8f8;font-weight:600;"
                if tag == "th"
                else "padding:10px 12px;border:1px solid #e6deef;text-align:left;background:#fff;"
            )
            cells.append(f"<{tag} style=\"{style}\">{escape(text)}</{tag}>")
        if cells:
            rows.append(f"<tr>{''.join(cells)}</tr>")
    if not rows:
        return ""
    return (
        '<section style="margin:18px 20px;overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;line-height:1.7;">'
        f"{''.join(rows)}"
        "</table></section>"
    )


def normalize_paragraph(text: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    text = re.sub(r"^\[图片\]\s*", "", text)
    text = re.sub(r"\s*\[图片\]\s*$", "", text)
    if text == "[图片]":
        return ""
    return text.strip()


def clean_generated_title(title: str) -> str:
    title = title.replace("\xa0", " ").strip()
    title = re.sub(r"^\[\d{8,}\]", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    return title


def render(template_path: Path, title: str, title_line: str, rewrite_html: Dict[str, str], family: str, style: str) -> str:
    meta = COLOR_META[family][style]
    usp = make_usp(title, rewrite_html["summary"])
    template = template_path.read_text(encoding="utf-8")
    html = template
    html = html.replace("__TITLE__", escape(title))
    html = html.replace("__SUBTITLE__", escape(usp))
    html = html.replace("__META__", title_line)
    html = html.replace("__TITLE_LINE__", escape(title_line))
    html = html.replace("__SUMMARY__", escape(rewrite_html["summary"]))
    html = html.replace("__INTRO__", rewrite_html["intro"])
    html = html.replace("__BODY__", rewrite_html["body"])
    html = html.replace("__MAIN__", meta["main"])
    html = html.replace("__ACCENT__", meta["accent"])
    html = html.replace("__BG__", meta["bg"])
    html = html.replace("__XYB_FOOTER__", DEFAULT_FOOTER.replace("__MAIN__", meta["main"]))
    return remove_empty_sections(html)


def remove_empty_sections(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    changed = True
    while changed:
        changed = False
        for tag in list(soup.find_all("section")):
            if is_empty_tag(tag):
                tag.decompose()
                changed = True
    return str(soup)


def choose_template(family: str, style: str) -> Path:
    key = (family, style)
    if key not in TEMPLATES:
        raise ValueError(f"unsupported template choice: {family}/{style}")
    return TEMPLATES[key]


def detect_input(source: str) -> Tuple[str, Path | None]:
    if re.match(r"^https?://", source):
        return "url", None
    return "path", Path(source).expanduser().resolve()


def prompt_choice(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def ensure_choices(args) -> Tuple[str, str, str]:
    family = args.template_family or prompt_choice("Choose template family: template1/template2/template3", "template1")
    if family == "template3":
        style = "raw_original"
    else:
        style = args.style or prompt_choice("Choose style: morandi_purple/morandi_green", "morandi_purple")
    rewrite_req = args.rewrite or input("Enter rewrite requirements: ").strip()
    return family, style, rewrite_req


def main() -> int:
    parser = argparse.ArgumentParser(description="XYB WeChat Transcribe skill")
    parser.add_argument("source", help="mp.weixin.qq.com URL or local file path")
    parser.add_argument("--template-family", choices=["template1", "template2", "template3"], help="Template family")
    parser.add_argument("--style", choices=["morandi_purple", "morandi_green", "raw_original"], help="Template style")
    parser.add_argument("--rewrite", default="", help="Rewrite requirements")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation prompts")
    args = parser.parse_args()

    family, style, rewrite_req = ensure_choices(args)

    kind, path = detect_input(args.source)
    if kind == "url":
        source_path = download_article(args.source, Path(args.output_dir))
    else:
        if not path or not path.exists():
            raise FileNotFoundError(f"input file not found: {args.source}")
        source_path = path

    title, body = read_source(source_path)
    mode = get_template_mode(family, style)
    rewrite_html = rewrite_article(title, body, rewrite_req, mode)
    template_path = choose_template(family, style)
    title_line = f"xyb-wechat-transcribe | {family} | {style}"
    html = render(template_path, title, title_line, rewrite_html, family, style)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", title).strip("_") or "xyb_article"
    out_path = out_dir / f"{safe_title}_公众号_{style}.html"
    out_path.write_text(html, encoding="utf-8")
    print(str(out_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
