"""seq_lines.py IN.json OUT.txt : MR lines for page-confirmed sequence proposals (read-only on the database).
Finds the read label at a line start ('LABEL.' / 'LABEL,' / 'LABEL .') in the unit's first block and writes
MR|doc|page|block|before|after|defect|observed; before carries the following words so it is unique in the block."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
xs = json.load(open(sys.argv[1], encoding="utf-8"))
lines = []
with connect() as conn, conn.cursor() as cur:
    for x in xs:
        cur.execute("SELECT text FROM text_block WHERE id=%s", (x["block"],))
        t = cur.fetchone()[0]
        m = re.search(rf"(?m)(?:^|(?<=\s))[^\w\n]{{0,2}}{re.escape(x['label'])}\s?[.,]", t)
        if not m:
            print("NO MATCH", x["doc"], x["block"], repr(t[:80])); continue
        end = m.end()
        tail = t[end:end + 25].split("\n")[0]
        before = t[m.start():end] + tail
        before = before.lstrip()
        after = before.replace(x["label"], x["proposed"], 1)
        if t.count(before) != 1:
            print("NOT UNIQUE", x["doc"], repr(before)); continue
        body = re.sub(r"\s+", " ", t[end:end + 140]).strip()
        defect = (f"{'the kept unit' if x['role'] == 'K' else 'the demoted unit'} printed '{x['proposed']}.' was read as "
                  f"'{x['label']}.' (a misread figure: its neighbours in the source run leave only {x['proposed']} free) "
                  f"and collided with the unit printed '{x['label']}'")
        obs = (f"Page {x['page']} prints '{x['proposed']}. {body} ...' -- the figure is plainly {x['proposed']} on the "
               f"page image, between the units printed {int(x['proposed']) - 1} and {int(x['proposed']) + 1}.")
        lines.append("|".join(["MR", str(x["doc"]), str(x["page"]), str(x["block"]), before, after, defect, obs]))
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(len(lines), "lines")
