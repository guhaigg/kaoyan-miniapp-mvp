#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


def _selector_payload(page, selector: str) -> dict[str, object]:
    locator = page.locator(selector)
    count = locator.count()
    texts: list[str] = []
    hrefs: list[str] = []
    for index in range(min(count, 5)):
        row = locator.nth(index)
        text = (row.inner_text(timeout=1000) or "").strip()
        if text:
            texts.append(text)
        href = row.get_attribute("href", timeout=1000)
        if href:
            hrefs.append(href)
    return {
        "selector": selector,
        "count": count,
        "sample_texts": texts,
        "sample_hrefs": hrefs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Minimal smoke test runner for Lightpanda via Playwright CDP."
    )
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="Lightpanda CDP endpoint URL.")
    parser.add_argument("--url", required=True, help="Target URL to navigate.")
    parser.add_argument(
        "--wait-until",
        default="networkidle",
        choices=["load", "domcontentloaded", "networkidle", "commit"],
        help="Playwright wait strategy for page.goto().",
    )
    parser.add_argument("--timeout-ms", type=int, default=15000, help="Navigation and selector timeout in milliseconds.")
    parser.add_argument(
        "--selector",
        action="append",
        default=[],
        help="Optional CSS selector to inspect. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dump-html",
        default="",
        help="Optional file path to write the final page HTML.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the JSON result without the summary prefix.",
    )
    args = parser.parse_args()

    result: dict[str, object] = {
        "engine": "lightpanda",
        "cdp_url": args.cdp_url,
        "requested_url": args.url,
        "wait_until": args.wait_until,
        "timeout_ms": args.timeout_ms,
        "ok": False,
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=args.timeout_ms)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.new_page()
                page.set_default_timeout(args.timeout_ms)
                response = page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout_ms)
                html = page.content()
                if args.dump_html:
                    output_path = Path(args.dump_html)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(html, encoding="utf-8")
                result.update(
                    {
                        "ok": True,
                        "status": response.status if response is not None else None,
                        "final_url": page.url,
                        "title": page.title(),
                        "content_length": len(html),
                        "selectors": [_selector_payload(page, selector) for selector in args.selector],
                    }
                )
            finally:
                browser.close()
    except PlaywrightError as exc:
        result["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_only:
        print(payload)
    else:
        print("Lightpanda smoke result:")
        print(payload)
    return 0 if bool(result["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
