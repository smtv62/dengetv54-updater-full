#!/usr/bin/env python3
import os
import re
import time
import json
from datetime import datetime, timedelta
from httpx import Client, RequestError
import requests
from urllib.parse import quote_plus

CACHE_FILE = "cache.json"
CACHE_TTL_SECONDS = 12 * 60 * 60  # 12 hours

class Dengetv54Manager:
    def __init__(self):
        self.httpx = Client(timeout=10, verify=True)
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
        self.base_stream_url = self.find_base_stream_url()
        self.dengetv_url = self.find_working_dengetv()

    def find_working_dengetv(self, start=67, end=200):
        headers = {"User-Agent": "Mozilla/5.0"}
        for i in range(start, end+1):
            url = f"https://dengetv{i}.live/"
            try:
                r = self.httpx.get(url, headers=headers)
                if r.status_code == 200 and "m3u8" in (r.text or ""):
                    print(f"✅ Dengetv: Çalışan domain bulundu -> {url}")
                    return url
            except RequestError:
                continue
        print("⚠️ Dengetv: Çalışan domain bulunamadı, varsayılan kullanılıyor.")
        return "https://dengetv58.live/"

    def query_crtsh(self, pattern="zirvedesin"):
        q = quote_plus(f"%{pattern}%")
        url = f"https://crt.sh/?q={q}&output=json"
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return []
            entries = r.json()
        except Exception:
            return []

        hosts = set()
        for e in entries:
            name = e.get("name_value") or ""
            for candidate in name.splitlines():
                candidate = candidate.strip()
                if "zirvedesin" in candidate and candidate.endswith(".sbs"):
                    candidate = candidate.lstrip("*.")
                    hosts.add(candidate)
        return sorted(hosts)

    def validate_hosts_for_yayin(self, hosts, path="/yayinzirve.m3u8", timeout=8):
        client = Client(timeout=timeout, verify=True)
        working = []
        for host in hosts:
            url = f"https://{host}{path}"
            try:
                r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and r.text and r.text.strip():
                    working.append(f"https://{host}/")
            except RequestError:
                continue
        return working

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

    def find_base_stream_url(self):
        cache = self._load_cache()
        now_ts = time.time()
        if cache.get("base_stream_url") and cache.get("base_ts") and (now_ts - cache.get("base_ts",0) < CACHE_TTL_SECONDS):
            return cache["base_stream_url"]

        hosts = self.query_crtsh("zirvedesin")
        if hosts:
            working = self.validate_hosts_for_yayin(hosts)
            if working:
                base = working[0]
                cache["base_stream_url"] = base
                cache["base_ts"] = now_ts
                self._save_cache(cache)
                print(f"✅ Zirvedesin: Çalışan domain bulundu -> {base}")
                return base

        common_subs = ["tible","kodiaq","stream","live","media","cdn","video"]
        for sub in common_subs:
            for n in range(10, 60):
                host = f"{sub}.zirvedesin{n}.sbs"
                url = f"https://{host}/yayinzirve.m3u8"
                try:
                    r = self.httpx.get(url, headers={"User-Agent":"Mozilla/5.0"})
                    if r.status_code == 200 and r.text and r.text.strip():
                        base = f"https://{host}/"
                        cache["base_stream_url"] = base
                        cache["base_ts"] = now_ts
                        self._save_cache(cache)
                        print(f"✅ Zirvedesin (heuristic): Çalışan domain bulundu -> {base}")
                        return base
                except RequestError:
                    continue

        print("⚠️ Zirvedesin: Domain bulunamadı, varsayılan kullanılıyor.")
        default = "https://tible.zirvedesin13.sbs/"
        cache["base_stream_url"] = default
        cache["base_ts"] = now_ts
        self._save_cache(cache)
        return default

    def calistir(self):
        m3u = ["#EXTM3U"]
        for _, file_name in self.channel_files.items():
            channel_name = re.sub(r'(\\d+)', r' \\1', file_name.replace(".m3u8","")).title()
            m3u.append(f'#EXTINF:-1 group-title="Dengetv54",{channel_name}')
            m3u.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u.append(f'#EXTVLCOPT:http-referrer={self.dengetv_url}')
            m3u.append(f'{self.base_stream_url}{file_name}')

        content = "\\n".join(m3u)
        os.makedirs("output", exist_ok=True)
        output_path = "output/dengetv54.m3u"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ M3U dosyası başarıyla güncellendi → {output_path}")
        return content


if __name__ == "__main__":
    m = Dengetv54Manager()
    m.calistir()
