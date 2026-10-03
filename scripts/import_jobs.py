"""Convert a job-postings CSV into data/jobs.json.
Usage: python scripts/import_jobs.py my_jobs.csv --source "Kaggle: <dataset name> (<license>)" [--append] [--limit 300]
Required skills are found with the app's skill taxonomy. Sentences containing words like
'preferred' / 'nice to have' / 'bonus' count as preferred skills. This is a heuristic: spot-check results."""
import csv, json, re, sys, argparse, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.engine import find_skills

COLS = {"title": ["title", "job_title", "jobtitle", "position"], "company": ["company", "company_name", "employer"],
        "location": ["location", "job_location", "city"], "description": ["description", "job_description", "details", "summary"]}
PREF = re.compile(r"preferred|nice to have|bonus|good to have|a plus", re.I)

def pick(row, names):
    for k, v in row.items():
        if k and k.strip().lower() in names and v and v.strip(): return v.strip()
    return ""

def convert(row, source):
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pick(row, COLS["description"])))
    title = pick(row, COLS["title"])
    if not title or not desc: return None
    req, pre = set(), set()
    for sent in re.split(r"(?<=[.!?])\s+", desc): (pre if PREF.search(sent) else req).update(find_skills(sent))
    if not req: return None  # nothing to score against
    loc, low = pick(row, COLS["location"]) or "Unspecified", (title + " " + desc).lower()
    yrs = re.search(r"(\d+)\+?\s*(?:years|yrs)", desc, re.I)
    mode = "remote" if "remote" in loc.lower() or "remote" in low else "hybrid" if "hybrid" in low else "on-site"
    typ = "internship" if "intern" in title.lower() else "contract" if "contract" in low else "full-time"
    return {"title": title, "company": pick(row, COLS["company"]) or "Unknown", "location": loc, "mode": mode, "type": typ,
            "min_years": min(int(yrs.group(1)), 10) if yrs else 0, "required": sorted(req), "preferred": sorted(pre - req),
            "description": desc[:1500], "source": source}

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("csv"); a.add_argument("--source", required=True)
    a.add_argument("--out", default=str(ROOT/"data"/"jobs.json")); a.add_argument("--append", action="store_true"); a.add_argument("--limit", type=int, default=400)
    a = a.parse_args(argv); out = pathlib.Path(a.out)
    jobs = json.loads(out.read_text()) if a.append and out.exists() else []
    seen = {(j["title"].lower(), j["company"].lower()) for j in jobs}; nid = max([j["id"] for j in jobs], default=0) + 1; skipped = 0
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if len(jobs) >= a.limit: break
            j = convert(row, a.source)
            if not j or (j["title"].lower(), j["company"].lower()) in seen: skipped += 1; continue
            seen.add((j["title"].lower(), j["company"].lower())); j["id"] = nid; nid += 1; jobs.append(j)
    out.write_text(json.dumps(jobs, indent=1)); print(f"Wrote {len(jobs)} jobs to {out} (skipped {skipped}: duplicates, missing fields or no recognizable skills)")
    return jobs

if __name__ == "__main__": main()
