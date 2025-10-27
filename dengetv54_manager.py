#!/usr/bin/env python3
import os
import re
import json
import asyncio
import time
from datetime import datetime
from httpx import AsyncClient, RequestError
from urllib.parse import quote_plus

CACHE_FILE = "cache.json"
CACHE_TTL_SECONDS = 12 * 60 * 60  # 12 saat cache

class Dengetv54Manager:
    def __init__(self):
        self.channel_files = {
            1: "yayinzirve.m3u8", 2: "yayin1.m3u8", 3: "yayininat.m3u8", 4: "yayinb2.m3u8",
            5: "yayinb3.m3u8", 6: "yayinb4.m3u8", 7: "yayinb5.m3u8", 8: "yayinbm1.m3u8",
            9: "yayinbm2.m3u8", 10: "yayinss.m3u8", 11: "yayinss2.m3u8", 13: "yayint1.m3u8",
            14: "yayint2.m3u8", 15: "yayint3.m3u8", 16: "yayinsmarts.m3u8", 17: "yayinsms2.m3u8",
            18: "yayintrtspor.m3u8", 19: "yayintrtspor2.m3u8", 20: "yayintrt1.m3u8",
            21: "yayinas.m3u8", 22: "yayinatv.m3u8", 23: "yayintv8.m3u8", 24: "yayintv85.m3u8",
            25: "yayinf1.m3u8", 26: "yayinnbatv.m3u8", 27: "yayineu1.m3u8", 28: "yayineu2.m3u8",
            29: "yayinex1.m3u8", 30: "yayinex2.m3u8", 31: "yayinex3.m3u8", 32: "yayinex4.m3u8",
            33: "yayinex5.m3u8", 34: "yayinex6.m3u8", 35: "yayinex7.m3u8", 36: "yayinex8.m3u8"
        }
        # placeholder, computed lazily in calistir()
        self.base_stream_url = None
        self.dengetv_url = None

    # ---------- cache helpers ----------
    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _save_cache(self, data):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- crt.sh query (async via HTTPX) ----------
    async def query_crtsh(self, pattern="zirvedesin"):
        q = quote_plus(f"%{pattern}%")
        url = f"https://crt.sh/?q={q}&output=json"
        try:
            async with AsyncClient(timeout=20) as client:
                r = await client.get(url, headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code != 200:
                    return []
                entries = r.json()
        except Exception:
            # fallback: return empty
            return []

        hosts = set()
        # entries may be a coroutine if using AsyncClient.json() incorrectly; ensure dict
        try:
            # if entries is coroutine-like, coerce
            if asyncio.iscoroutine(entries):
                entries = await entries
        except Exception:
            pass

        # entries expected to be a list of dicts
        for e in entries:
            name = e.get("name_value") if isinstance(e, dict) else ""
            if not name:
                continue
            for candidate in str(name).splitlines():
                candidate = candidate.strip()
                if "zirvedesin" in candidate and candidate.endswith(".sbs"):
                    candidate = candidate.lstrip("*.")  # remove wildcard prefix
                    hosts.add(candidate)
        return sorted(hosts)

    # ---------- host validator ----------
    async def validate_host(self, client: AsyncClient, host: str, path: str = "/yayinzirve.m3u8"):
        url = f"https://{host}{path}"
        try:
            r = await client.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200 and r.text and r.text.strip():
                return f"https://{host}/"
        except RequestError:
            return None
        except Exception:
            return None
        return None

    # ---------- attempt to extract .sbs hosts from dengetv pages ----------
    async def extract_hosts_from_dengetv_pages(self, start=67, end=200, max_pages=20):
        """
        Sequentially request dengetv pages (starting from start) and parse HTML for .sbs hostnames.
        Stops early when enough candidates found or limit reached.
        This helps discover hosts embedded in provider pages (very effective).
        """
        found = set()
        headers = {"User-Agent":"Mozilla/5.0"}
        count = 0
        async with AsyncClient(timeout=6) as client:
            for i in range(start, end+1):
                url = f"https://dengetv{i}.live/"
                try:
                    r = await client.get(url, headers=headers)
                    if r.status_code == 200 and r.text:
                        # find things like "kodiaq.zirvedesin24.sbs" or "something.zirvedesin24.sbs"
                        for match in re.findall(r'([a-z0-9\-\_\.]+zirvedesin\d+\.sbs)', r.text, flags=re.IGNORECASE):
                            found.add(match.lstrip("*."))
                        count += 1
                        if count >= max_pages:
                            break
                except Exception:
                    # continue to next domain
                    continue
        return sorted(found)

    # ---------- main base stream discovery ----------
    async def find_base_stream_url(self):
        cache = self._load_cache()
        now_ts = time.time()
        if cache.get("base_stream_url") and cache.get("base_ts") and (now_ts - cache.get("base_ts", 0) < CACHE_TTL_SECONDS):
            return cache["base_stream_url"]

        # 1) Try crt.sh discovered hosts
        hosts = await self.query_crtsh("zirvedesin")
        if hosts:
            async with AsyncClient(timeout=6) as client:
                tasks = [self.validate_host(client, h) for h in hosts]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                working = [r for r in results if isinstance(r, str) and r]
                if working:
                    base = working[0]
                    cache["base_stream_url"] = base
                    cache["base_ts"] = now_ts
                    self._save_cache(cache)
                    print(f"✅ Zirvedesin (crt.sh): Çalışan domain bulundu -> {base}")
                    return base

        # 2) Try extracting hosts from dengetv pages (very high chance)
        candidates = await self.extract_hosts_from_dengetv_pages(start=67, end=200, max_pages=30)
        if candidates:
            async with AsyncClient(timeout=6) as client:
                tasks = [self.validate_host(client, h) for h in candidates]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                working = [r for r in results if isinstance(r, str) and r]
                if working:
                    base = working[0]
                    cache["base_stream_url"] = base
                    cache["base_ts"] = now_ts
                    self._save_cache(cache)
                    print(f"✅ Zirvedesin (from dengetv pages): Çalışan domain bulundu -> {base}")
                    return base

        # 3) Heuristic brute-force (common subdomains + numeric suffix)
        common_subs = ["kodiaq","kodiaq","stream","live","media","cdn","video","player"]
        # prepare candidate list (limit breadth to avoid huge scan)
        candidates = [f"{sub}.zirvedesin{n}.sbs" for sub in common_subs for n in range(10, 80)]
        async with AsyncClient(timeout=5) as client:
            tasks = [self.validate_host(client, h) for h in candidates]
            # run in chunks to avoid resource overwhelm
            chunk_size = 200
            for i in range(0, len(tasks), chunk_size):
                chunk = tasks[i:i+chunk_size]
                results = await asyncio.gather(*chunk, return_exceptions=True)
                working = [r for r in results if isinstance(r, str) and r]
                if working:
                    base = working[0]
                    cache["base_stream_url"] = base
                    cache["base_ts"] = now_ts
                    self._save_cache(cache)
                    print(f"✅ Zirvedesin (heuristic): Çalışan domain bulundu -> {base}")
                    return base

        # 4) fallback default
        default = "https://kodiaq.zirvedesin24.sbs/"
        cache["base_stream_url"] = default
        cache["base_ts"] = now_ts
        self._save_cache(cache)
        print("⚠️ Zirvedesin: Domain bulunamadı, varsayılan kullanılıyor.")
        return default

    # ---------- dengetv discovery: sequential increment as requested ----------
    async def find_working_dengetv(self, start=67, end=200):
        headers = {"User-Agent":"Mozilla/5.0"}
        async with AsyncClient(timeout=5) as client:
            for i in range(start, end+1):
                url = f"https://dengetv{i}.live/"
                try:
                    r = await client.get(url, headers=headers)
                    if r.status_code == 200 and r.text and "m3u8" in r.text:
                        print(f"✅ Dengetv: Çalışan domain bulundu -> {url}")
                        return url
                except Exception:
                    continue
        print("⚠️ Dengetv: Çalışan domain bulunamadı, varsayılan kullanılıyor.")
        return "https://dengetv67.live/"

    # ---------- generate m3u ----------
    async def calistir(self):
        # discover sources
        self.base_stream_url = await self.find_base_stream_url()
        self.dengetv_url = await self.find_working_dengetv(start=67, end=200)

        m3u = ["#EXTM3U"]
        for _, file_name in self.channel_files.items():
            channel_name = re.sub(r'(\d+)', r' \1', file_name.replace(".m3u8", "")).title()
            m3u.append(f'#EXTINF:-1 group-title="Dengetv54",{channel_name}')
            m3u.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u.append(f'#EXTVLCOPT:http-referrer={self.dengetv_url}')
            m3u.append(f'{self.base_stream_url}{file_name}')

        content = "\n".join(m3u)

        # write output
        os.makedirs("output", exist_ok=True)
        output_path = "output/dengetv54.m3u"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ M3U dosyası başarıyla güncellendi → {output_path}")
        return content


if __name__ == "__main__":
    mgr = Dengetv54Manager()
    asyncio.run(mgr.calistir())
