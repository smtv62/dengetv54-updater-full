#!/usr/bin/env python3
from dengetv54_manager import Dengetv54Manager
from datetime import datetime
import os

def main():
    manager = Dengetv54Manager()
    content = manager.calistir()
    print(datetime.utcnow().isoformat() + "Z - M3U created")
    return content

if __name__ == "__main__":
    main()
