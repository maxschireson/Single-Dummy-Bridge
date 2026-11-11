from pathlib import Path
import gzip,hashlib,json
r=Path(__file__).resolve().parent
b=gzip.decompress(b"".join(p.read_bytes() for p in sorted((r/"corpus-parts").glob("*.part-*"))))
assert hashlib.sha256(b).hexdigest()==json.loads((r/"manifest.json").read_text())["corpus_sha256"]
(r/"corpus.jsonl").write_bytes(b)
print("Corpus restored and SHA256 verified")
