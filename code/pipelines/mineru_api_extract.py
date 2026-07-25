# -*- coding: utf-8 -*-
"""MinerU API 批量 PDF→Markdown 转换脚本

流程（对每个 PDF）：
1. POST /api/v4/file-urls/batch  申请上传 URL
2. PUT 上传 PDF 原始字节
3. GET /api/v4/extract-results/batch/{batch_id}  轮询直到 done
4. 下载 full_zip_url 解压到 refs/mineru_vlm_output/<pdf_name>/

用 vlm 模型（最优质，复杂布局/公式/表格）。
"""
import os
import sys
import json
import time
import zipfile
import requests
from pathlib import Path

# ---------- 配置 ----------
TOKEN_FILE = r"C:\Users\Lee\.mineru_token"
REFS_DIR = r"D:\Pythonfiles\pythonProject\shipping_wasp\refs"
OUTPUT_DIR = REFS_DIR + r"\mineru_vlm_output"
BASE_URL = "https://mineru.net"
MODEL_VERSION = "vlm"   # 最佳质量，公式/表格全开

# 待处理 9 篇（已有 pdfplumber 但缺公式/表格，需要 vlm 重提）
TARGET_PDFS = [
    "Odyssa   a techno-economic evaluation framework for wind-assisted vessels with hydrogeneration.pdf",
    "Kuhl_2025_Flettner_CFD_arXiv.pdf",
    "energies-18-00897.pdf",
    "jmse-12-00485.pdf",
    "jmse-12-01645.pdf",
    "jmse-13-01287-v3.pdf",
    "IET Intelligent Trans Sys - 2025 - Song - An Optimal Energy‐Saving Coordination Control System for Sail‐Propeller of.pdf",
    "A_与NSGA-II融合的船舶气象航线多目标规划方法_李元奎.pdf",
    "Fourth IMO GHG Study 2020 Executive-Summary.pdf",
]


def load_token():
    if not os.path.exists(TOKEN_FILE):
        sys.exit(f"Token file not found: {TOKEN_FILE}")
    with open(TOKEN_FILE, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            s = line.strip()
            if s and not s.startswith("#"):
                # strip < > brackets
                return s.strip("<>").strip()
    sys.exit("Token file has no non-comment non-empty line")


def request_upload_url(token, file_name, data_id="mine-001"):
    """申请一个上传 URL"""
    url = f"{BASE_URL}/api/v4/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = {
        "files": [{"name": file_name, "data_id": data_id}],
        "model_version": MODEL_VERSION,
        "enable_formula": True,
        "enable_table": True,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"申请上传 URL 失败: {json.dumps(j, ensure_ascii=False)[:500]}")
    data = j["data"]
    return data["batch_id"], data["file_urls"][0]


def upload_file(upload_url, file_path):
    """PUT 上传原始字节"""
    with open(file_path, "rb") as fh:
        content = fh.read()
    r = requests.put(upload_url, data=content, timeout=300)
    r.raise_for_status()


def poll_batch(token, batch_id, timeout_s=1800, interval=8):
    """轮询 batch 状态直到 done/failed"""
    url = f"{BASE_URL}/api/v4/extract-results/batch/{batch_id}"
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    last_state = None
    while time.time() - start < timeout_s:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 0:
            raise RuntimeError(f"轮询失败: {json.dumps(j, ensure_ascii=False)[:500]}")
        extract = j["data"]["extract_result"][0]
        state = extract["state"]
        if state != last_state:
            elapsed = int(time.time() - start)
            print(f"    [{elapsed:>3}s] state: {state}")
            last_state = state
        if state == "done":
            return extract
        if state == "failed":
            raise RuntimeError(f"解析失败: {extract.get('err_msg','')}")
        time.sleep(interval)
    raise TimeoutError(f"轮询超时 {timeout_s}s")


def download_and_extract(zip_url, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    zip_path = out_dir + ".zip"
    print(f"    下载 zip -> {zip_path}")
    with requests.get(zip_url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as fh:
            for chunk in r.iter_content(8192):
                fh.write(chunk)
    print(f"    解压 -> {out_dir}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    os.remove(zip_path)


def process_one(token, pdf_path, out_root):
    name = os.path.basename(pdf_path)
    stem = os.path.splitext(name)[0]
    # 简化输出目录名（避免太长）
    safe_stem = stem.replace(" ", "_").replace(":", "_")[:80]
    out_dir = os.path.join(out_root, safe_stem)
    if os.path.exists(out_dir) and os.listdir(out_dir):
        print(f"  [SKIP] 已存在: {out_dir}")
        return
    print(f"\n=== {name} ===")
    size_mb = os.path.getsize(pdf_path) / 1024 / 1024
    print(f"  文件大小: {size_mb:.1f} MB")
    print(f"  申请上传 URL...")
    batch_id, upload_url = request_upload_url(token, name, data_id=safe_stem)
    print(f"  batch_id: {batch_id}")
    print(f"  上传文件...")
    upload_file(upload_url, pdf_path)
    print(f"  轮询解析状态...")
    extract = poll_batch(token, batch_id)
    zip_url = extract.get("full_zip_url")
    if not zip_url:
        # 单文件 url 可能是 full_markdown_url 等
        print(f"  无 full_zip_url，提取结果键: {list(extract.keys())}")
        # 试试看有没有其它可用 URL
        for k in ("full_markdown_url", "full_page Gerry_url", "raw_pdf_url"):
            if extract.get(k):
                print(f"  用 {k}: {extract[k]}")
                zip_url = extract[k]
                break
    if not zip_url:
        raise RuntimeError(f"未找到下载 URL，extract 字段: {json.dumps(extract, ensure_ascii=False)[:500]}")
    download_and_extract(zip_url, out_dir)
    # 列出产物
    files = sorted(os.listdir(out_dir))
    print(f"  产物 ({len(files)} 个): {files[:8]}{'...' if len(files) > 8 else ''}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    token = load_token()
    print(f"Token loaded: {token[:6]}...{token[-4:]}  len={len(token)}")
    print(f"输出根目录: {OUTPUT_DIR}")
    print(f"待处理 PDF: {len(TARGET_PDFS)} 篇")
    # 允许命令行传一个 PDF 名做单文件测试
    if len(sys.argv) > 1:
        target = sys.argv[1]
        TARGET_PDFS[:] = [p for p in TARGET_PDFS if target.lower() in p.lower()]
        print(f"过滤后: {TARGET_PDFS}")
    summary = []
    for pdf_name in TARGET_PDFS:
        pdf_path = os.path.join(REFS_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"\n[MISS] 文件不存在: {pdf_path}")
            summary.append((pdf_name, "MISS"))
            continue
        try:
            process_one(token, pdf_path, OUTPUT_DIR)
            summary.append((pdf_name, "OK"))
        except Exception as e:
            print(f"  [ERROR] {e}")
            summary.append((pdf_name, f"ERR: {e}"))
    print("\n=== 汇总 ===")
    for n, s in summary:
        print(f"  {s:8}  {n}")


if __name__ == "__main__":
    main()
