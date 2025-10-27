#!/usr/bin/env python3
import os
import re
import json
import asyncio
from datetime import datetime
from httpx import AsyncClient, RequestError
import aiohttp
from urllib.parse import quote_plus
import time

CACHE_FILE = "cache.json"
CACHE_TTL_SECONDS = 12 * 60 * 60  # 12 saat

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
        self.base_stream_url = None
        self.dengetv_url = None

    # ---------- Cache helper ----------
    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self, data):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- crt.sh async query ----------
    async def query_crtsh(self, pattern="zirvedesin"):
        url = f"https://crt.sh/?q={quote_plus(f'%{pattern}%')}&output=json"
        hosts = set()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=20) as resp:
                    if resp.status != 200:
                        return []
                    entries = await resp.json()
        except Exception:
            return []

        for e in entries:
            name = e.get("name_value") or ""
            for candidate in name.splitlines():
                candidate = candidate.strip()
                if "zirvedesin" in candidate and candidate.endswith(".sbs"):
                    hosts.add(candidate.lstrip("*."))
        return sorted(hosts)

    async def validate_host(self, client, host, path="/yayinzirve.m3u8"):
        url = f"https://{host}{path}"
        try:
            r = await client.get(url, timeout=8)
            if r.status_code == 200 and r.text.strip():
                return f"https://{host}/"
        except RequestError:
            return None
        return None

    async def find_base_stream_url(self):
        cache = self._load_cache()
        now_ts = time.time()
        if cache.get("base_stream_url") and cache.get("base_ts") and (now_ts - cache.get("base_ts",0) < CACHE_TTL_SECONDS):
            return cache["base_stream_url"]

        hosts = await self.query_crtsh("zirvedesin")
        async with AsyncClient(timeout=8, verify=True) as client:
            tasks = [self.validate_host(client, h) for h in hosts]
            results = await asyncio.gather(*tasks)
            working = [r for r in results if r]
            if working:
                base = working[0]
                cache["base_stream_url"] = base
                cache["base_ts"] = now_ts
                self._save_cache(cache)
                print(f"✅ Zirvedesin: Çalışan domain bulundu -> {base}")
                return base

        # fallback heuristic
        common_subs = ["tible","kodiaq","stream","live","media","cdn","video"]
        async with AsyncClient(timeout=8, verify=True) as client:
            tasks = []
            for sub in common_subs:
                for n in range(10,60):
                    tasks.append(self.validate_host(client, f"{sub}.zirvedesin{n}.sbs"))
            results = await asyncio.gather(*tasks)
            working = [r for r in results if r]
            if working:
                base = working[0]
                cache["base_stream_url"] = base
                cache["base_ts"] = now_ts
                self._save_cache(cache)
                print(f"✅ Zirvedesin (heuristic): Çalışan domain bulundu -> {base}")
                return base

        default = "https://tible.zirvedesin13.sbs/"
        cache["base_stream_url"] = default
        cache["base_ts"] = now_ts
        self._save_cache(cache)
        print("⚠️ Zirvedesin: Domain bulunamadı, varsayılan kullanılıyor.")
        return default

    async def find_working_dengetv(self, start=67, end=200):
        async with AsyncClient(timeout=5) as client:
            tasks = [client.get(f"https://dengetv{i}.live/", timeout=5) for i in range(start, end+1)]
            for i, task in enumerate(asyncio.as_completed(tasks), start=start):
                try:
                    r = await task
                    if r.status_code == 200 and "m3u8" in r.text:
                        print(f"✅ Dengetv: Çalışan domain bulundu -> https://dengetv{i}.live/")
                        return f"https://dengetv{i}.live/"
                except Exception:
                    continue
        print("⚠️ Dengetv: Çalışan domain bulunamadı, varsayılan kullanılıyor.")
        return "https://dengetv58.live/"

    # ---------- M3U generation ----------
    async def calistir(self):
        self.base_stream_url = await self.find_base_stream_url()
        self.dengetv_url = await self.find_working_dengetv()
        m3u = ["#EXTM3U"]
        for _, file_name in self.channel_files.items():
            channel_name = re.sub(r'(\d+)', r' \1', file_name.replace(".m3u8","")).title()
            m3u.append(f'#EXTINF:-1 group-title="Dengetv54",{channel_name}')
            m3u.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u.append(f'#EXTVLCOPT:http-referrer={self.dengetv_url}')
            m3u.append(f'{self.base_stream_url}{file_name}')
        content = "\n".join(m3u)
        os.makedirs("output", exist_ok=True)
        output_path = "output/dengetv54.m3u"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ M3U dosyası başarıyla güncellendi → {output_path}")
        return content


if __name__ == "__main__":
    manager = Dengetv54Manager()
    asyncio.run(manager.calistir())
