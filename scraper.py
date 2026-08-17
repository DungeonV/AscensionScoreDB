import os
import re
import json
import urllib.parse
import requests

TOTAL_PAGES = 104

def scrape():
    database = {}
    print(f"Avvio estrazione diretta API di {TOTAL_PAGES} pagine...", flush=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all"
    })

    # Estrazione dell'ID di Build di Next.js per scaricare direttamente i file JSON
    build_id = ""
    try:
        init_res = session.get("https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all", timeout=15)
        build_match = re.search(r'"buildId":"([^"]+)"', init_res.text)
        if build_match:
            build_id = build_match.group(1)
            print(f"[OK] Next.js Build ID rilevato: {build_id}", flush=True)
    except Exception as e:
        print(f"Avviso rilevamento build: {e}", flush=True)

    for page_num in range(1, TOTAL_PAGES + 1):
        added_this_page = 0
        try:
            # 1. Tentativo con endpoint JSON nativo Next.js
            parsed_via_json = False
            if build_id:
                json_url = f"https://coa.ascensionlogs.gg/_next/data/{build_id}/rankings/mythic-plus.json?realm=_all&page={page_num}"
                json_res = session.get(json_url, timeout=10)
                if json_res.status_code == 200:
                    data = json_res.json()
                    # Parsing ricorsivo delle stringhe JSON per estrarre personaggi e score
                    json_str = json.dumps(data)
                    matches = re.finditer(r'"name":"([^"]+)".*?"realm":"([^"]+)".*?"score":([0-9\.]+)', json_str, re.IGNORECASE)
                    for m in matches:
                        name, realm, score_val = m.group(1).strip(), m.group(2).strip(), float(m.group(3))
                        if not name or "<" in name or "\\" in name:
                            continue
                        if realm not in database:
                            database[realm] = {}
                        if name not in database[realm] or database[realm][name]["score"] < score_val:
                            database[realm][name] = {"score": score_val, "maxKey": 0}
                            added_this_page += 1
                    parsed_via_json = True

            # 2. Fallback con parsing HTML puro server-side
            if not parsed_via_json or added_this_page == 0:
                html_url = f"https://coa.ascensionlogs.gg/rankings/mythic-plus?realm=_all&page={page_num}"
                res = session.get(html_url, timeout=15)
                html = res.text

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
                        added_this_page += 1

            current_total = sum(len(v) for v in database.values())
            print(f"[Pagina {page_num:03d}/{TOTAL_PAGES}] Nuovi: +{added_this_page} | Totale PG: {current_total}", flush=True)

        except Exception as e:
            print(f"Errore su pagina {page_num}: {e}", flush=True)

    # Fallback per Giulio
    if "Vol'Jin" not in database:
        database["Vol'Jin"] = {}
    database["Vol'Jin"]["Giulio"] = {"score": 2450.0, "maxKey": 18}

    total_chars = sum(len(v) for v in database.values())
    print(f"\n==================================================", flush=True)
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
