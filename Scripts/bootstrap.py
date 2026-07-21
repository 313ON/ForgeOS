\
"""
ForgeOS Bootstrap v1.0.0
Creates initial project structure. Self-bootstrapping:
if Resources/bootstrap/structure.json does not exist,
it is generated from DEFAULT_STRUCTURE.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

VERSION="1.0.0"

DEFAULT_STRUCTURE={
    "directories":[
        "Backend","Backend/app","Backend/app/api","Backend/app/core",
        "Backend/app/models","Backend/app/repositories","Backend/app/schemas",
        "Backend/app/services","Backend/app/utils","Backend/tests",
        "Database","Deployment","Docs","Frontend","Logs",
        "Resources/assets","Resources/bootstrap","Resources/icons","Resources/templates"
    ],
    "files":[
        ".gitignore","README.md",
        "Backend/app/__init__.py","Backend/app/main.py",
        "Backend/app/core/__init__.py","Backend/app/core/logger.py"
    ]
}

class Bootstrap:
    def __init__(self, root:Path):
        self.root=root
        self.created=0
        self.skipped=0

    @property
    def structure(self)->Path:
        return self.root/"Resources"/"bootstrap"/"structure.json"

    def ensure_structure(self):
        self.structure.parent.mkdir(parents=True,exist_ok=True)
        if not self.structure.exists():
            self.structure.write_text(json.dumps(DEFAULT_STRUCTURE,indent=2),encoding="utf-8")
            print("[ OK ] Generated Resources/bootstrap/structure.json")

    def load(self):
        return json.loads(self.structure.read_text(encoding="utf-8"))

    def create(self):
        data=self.load()
        for d in data["directories"]:
            p=self.root/d
            if p.exists():
                self.skipped+=1
            else:
                p.mkdir(parents=True,exist_ok=True)
                self.created+=1
                print(f"[DIR ] {d}")
        for f in data["files"]:
            p=self.root/f
            if p.exists():
                self.skipped+=1
            else:
                p.parent.mkdir(parents=True,exist_ok=True)
                p.touch()
                self.created+=1
                print(f"[FILE] {f}")

    def run(self):
        t=time.perf_counter()
        self.ensure_structure()
        self.create()
        print(f"\nCreated: {self.created}  Skipped: {self.skipped}")
        print(f"Elapsed: {time.perf_counter()-t:.3f}s")

if __name__=="__main__":
    try:
        Bootstrap(Path(__file__).resolve().parent.parent).run()
    except Exception as e:
        print("[ERROR]",e)
        sys.exit(1)
