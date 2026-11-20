"""Regression guard for the generated FY_G75Tbl.

Checks the table written by patch_oc.py parses back to exactly the intended
ladders, with no duplicated/unsorted rows and the right number of entries.
Run after patch_oc.py:  python verify_pvt.py <kernel-root>
"""
import re
import sys
from pathlib import Path

PVT_H = ("drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6768/"
         "mtk_cpufreq_opp_pv_table.h")

EXPECT = {
    "L": [1800, 1625, 1500, 1450, 1375, 1325, 1275, 1230, 1175, 1111,
          1050, 999, 950, 850, 774, 350],
    "B": [2300, 2202, 2050, 1900, 1850, 1800, 1710, 1621, 1532, 1443,
          1354, 1295, 1176, 1087, 998, 350],
    "CCI": [1277, 1120, 1049, 1014, 961, 909, 856, 821, 768, 733, 698,
            663, 628, 593, 558, 350],
}

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
text = (root / PVT_H).read_text(encoding="utf-8")

m = re.search(r"FY_G75Tbl\[[^\]]+\]\[[^\]]+\] = \{[^\n]*\n(.*?)\n\};", text, re.S)
if not m:
    sys.exit("FY_G75Tbl not found")

body = m.group(1)
all_rows = re.findall(r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", body)
print("total OPP rows in FY_G75Tbl:", len(all_rows))
if len(all_rows) != 48:
    sys.exit("FAIL: expected 48 rows (3 clusters x 16), got %d" % len(all_rows))

ok = True
for tag, expect in EXPECT.items():
    mm = re.search(r"/\* *%s *\*/(.*?)(?=/\* *(?:L|B|CCI) *\*/|$)" % tag, body, re.S)
    rows = re.findall(r"\{\s*(\d+),\s*(\d+),\s*\d+,\s*\d+\s*\}", mm.group(1))
    freqs = [int(r[0]) for r in rows]
    status = "OK " if freqs == expect else "FAIL"
    if freqs != expect:
        ok = False
    print("%s %-4s %s" % (status, tag, " ".join(str(f) for f in freqs)))

sys.exit(0 if ok else 1)
