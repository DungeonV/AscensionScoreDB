import os
import re
import urllib.parse
import json
from playwright.sync_api import sync_playwright

TOTAL_PAGES = 104

def scrape():
    database = {}
    print(f"Avvio scansione progressiva di {TOTAL_PAGES} pagine...", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        page = context.new_page()

        # Funzione helper per parsare l'HTML
        def parse_current_html():
            html = page.content()
            matches = list(re.finditer(r'/characters/([^/"\?]+)/([^/"\?]+)', html, re.IGNORECASE))
            count = 0
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
                    count += 1
            return count

        # 1. Carica la leaderboard iniziale
        print("Caricamento iniziale della leaderboard...", flush=True)
        page.goto("https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        # 2. Ciclo di navigazione su tutte le 104 pagine
        for page_num in range(1, TOTAL_PAGES + 1):
            try:
                # Estrai dalla pagina corrente
                added = parse_current_html()
                current_total = sum(len(v) for v in database.values())
                print(f"[Pagina {page_num}/{TOTAL_PAGES}] Trovati: +{added} | Totale PG: {current_total}", flush=True)

                if page_num < TOTAL_PAGES:
                    # Tenta di cliccare la freccia o il numero di pagina successivo
                    next_clicked = False
                    
                    # Prova selettori multipli per il pulsante "Next"
                    possible_buttons = [
                        page.locator("button:has-text('Next')"),
                        page.locator("button:has-text('>')"),
                        page.locator("[aria-label*='next' i]"),
                        page.locator("nav button").last
                    ]

                    for btn in possible_buttons:
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            next_clicked = True
                            page.wait_for_timeout(1500)
                            break

                    # Se il bottone non è cliccabile, naviga forzatamente via URL nella stessa scheda
                    if not next_clicked:
                        next_url = f"https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all&page={page_num + 1}"
                        page.goto(next_url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1500)

            except Exception as e:
                print(f"Avviso su pagina {page_num}: {e}", flush=True)
                page.wait_for_timeout(2000)

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
