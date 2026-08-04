import hashlib
import sys
import zipfile
from pathlib import Path

source = Path(sys.argv[1])
output = Path(sys.argv[2])
lines = []
with zipfile.ZipFile(source) as archive:
    for name in sorted(archive.namelist()):
        data = archive.read(name)
        digest = hashlib.sha256(data).hexdigest()
        lines.append(f"{name}\t{len(data)}\t{digest}")
output.write_text("\n".join(lines) + "\n", encoding="utf-8")
