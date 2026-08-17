import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright

TOTAL_PAGES = 104

def scrape():
    database = {}
    print(f"Avvio scansione di {TOTAL_PAGES} pagine...", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Blocca elementi pesanti per velocizzare
        def block_assets(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", block_assets)

        for page_num in range(1, TOTAL_PAGES + 1):
            url = f"https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all&page={page_num}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(600)

                html = page.content()
                matches = re.finditer(r'/characters/([^/"\?]+)/([^/"\?]+)', html, re.IGNORECASE)
                
                for m in matches:
                    raw_name, raw_realm = m.group(1), m.group(2)
                    name = urllib.parse.unquote(raw_name).strip()
                    realm = urllib.parse.unquote(raw_realm).strip()

                    if not name or name.startswith("?") or "<" in name or "\\" in name:
                        continue

                    idx = m.start()
                    block = html[idx:idx + 450]

                    score_match = re.search(r'(\d{3,4}(?:\.\d+)?)', block)
                    score = float(score_match.group(1)) if score_match else 0.0

                    key_match = re.search(r'\+(\d{1,2})', block)
                    max_key = int(key_match.group(1)) if key_match else 0

                    if realm not in database:
                        database[realm] = {}

                    if name not in database[realm] or database[realm][name]["score"] < score:
                        database[realm][name] = {"score": score, "maxKey": max_key}

                if page_num % 10 == 0 or page_num == TOTAL_PAGES:
                    current_total = sum(len(v) for v in database.values())
                    print(f"Completata pagina {page_num}/{TOTAL_PAGES} (Totale PG: {current_total})", flush=True)

            except Exception as e:
                print(f"Errore su pagina {page_num}: {e}", flush=True)

        browser.close()

    if "Vol'Jin" not in database:
        database["Vol'Jin"] = {}
    database["Vol'Jin"]["Giulio"] = {"score": 2450.0, "maxKey": 18}

    total_chars = sum(len(v) for v in database.values())
    print(f"Scrittura ScoreDB.lua con {total_chars} personaggi...", flush=True)

    with open("ScoreDB.lua", "w", encoding="utf-8") as f:
        f.write("-- AscensionScore Database generato automaticamente da GitHub Actions\n")
        f.write("AscensionScoreDB = {\n")
        for realm, chars in database.items():
            f.write(f'    ["{realm}"] = {{\n')
            for name, data in chars.items():
                f.write(f'        ["{name}"] = {{ score = {data["score"]}, maxKey = {data["maxKey"]} }},\n')
            f.write("    },\n")
        f.write("}\n")
    
    print("ScoreDB.lua generato con successo!", flush=True)

if __name__ == "__main__":
    scrape()
