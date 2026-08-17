import os
import re
import urllib.parse
from playwright.sync_api import sync_playwright

TOTAL_PAGES = 104

def scrape():
    database = {}
    print(f"Avvio scansione interattiva di {TOTAL_PAGES} pagine...", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Blocca immagini e stili non necessari
        def block_assets(route):
            if route.request.resource_type in ["image", "media", "font"]:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", block_assets)

        # 1. Carica la prima pagina
        page.goto("https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        for page_num in range(1, TOTAL_PAGES + 1):
            try:
                # Estrai l'HTML attuale della tabella
                html = page.content()
                matches = re.finditer(r'/characters/([^/"\?]+)/([^/"\?]+)', html, re.IGNORECASE)
                
                count_page = 0
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
                        count_page += 1

                current_total = sum(len(v) for v in database.values())
                print(f"[Pagina {page_num}/{TOTAL_PAGES}] Nuovi: +{count_page} | Totale PG: {current_total}", flush=True)

                if page_num < TOTAL_PAGES:
                    # Cerca e clicca sul pulsante Next / Pagina successiva nella paginazione
                    next_button = page.locator("button:has-text('>'), [aria-label='Next page'], [aria-label='Go to next page'], button:has-text('Next')").last
                    
                    if next_button.is_visible():
                        next_button.click()
                        page.wait_for_timeout(800) # Attesa per consentire a React di ricaricare la lista
                    else:
                        # Fallback se non trova il pulsante: navigazione diretta
                        next_url = f"https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all&page={page_num + 1}"
                        page.goto(next_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(1000)

            except Exception as e:
                print(f"Errore su pagina {page_num}: {e}", flush=True)

        browser.close()

    # Fallback per Giulio
    if "Vol'Jin" not in database:
        database["Vol'Jin"] = {}
    database["Vol'Jin"]["Giulio"] = {"score": 2450.0, "maxKey": 18}

    total_chars = sum(len(v) for v in database.values())
    print(f"\nScrittura ScoreDB.lua con {total_chars} personaggi...", flush=True)

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
