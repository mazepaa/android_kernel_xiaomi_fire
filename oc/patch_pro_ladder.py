"""MT6768 CPU overclock: replace the PRO PVT tables' ladders.

Why: Xiaomi fire actually runs the PRO segment. Its live ladder (root procfs
`/proc/cpufreq/MT_CPU_DVFS_LL` and `MT_CPU_DVFS_L`) is
  little: 2100 1800 1625 1450 1375 1325 1275 1175 1100 1050 999 950 900 850 774 500
  big:    2300 2050 1900 1850 1800 1710 1621 1532 1443 1354 1295 1176 1087 998 774 500
which matches neither FY_G75Tbl nor FY_6768Tbl — it is proTbl / proTbl_v7 with an
OC top added. So the OC edits belong in proTbl / proTbl_v7.

The PVT tables carry 16 slots (NR_FREQ); extra entries beyond 16 are ignored by
the copy loop, so writing a 16-entry ladder is the only correct shape.

Usage: python patch_pro_ladder.py <kernel-root>
"""
import re
import sys
from pathlib import Path

PVT = ("drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6768/"
       "mtk_cpufreq_opp_pv_table.h")

# (freq MHz, Vproc in 10 mV)
LITTLE = [(1800, 81), (1625, 69), (1500, 63), (1450, 61), (1375, 57), (1325, 55),
          (1275, 53), (1230, 51), (1175, 48), (1111, 45), (1050, 42), (999, 39),
          (950, 37), (850, 32), (774, 28), (350, 24)]
BIG = [(2300, 112), (2202, 111), (2050, 109), (1900, 104), (1850, 103), (1800, 101),
       (1710, 98), (1621, 94), (1532, 91), (1443, 88), (1354, 84), (1295, 82),
       (1176, 78), (1087, 74), (998, 71), (350, 63)]
CCI = [(1477, 104), (1263, 98), (1049, 85), (1014, 84), (961, 81), (909, 79),
       (856, 78), (821, 76), (768, 74), (733, 73), (698, 71), (663, 69),
       (628, 68), (593, 67), (558, 65), (350, 65)]


def fmt(tbl):
    return "\n".join("\t{ %d, %d, %d, 1 }," % (f, v, 1 if f >= 1800 else 2) for f, v in tbl)


def render(table):
    return ("static unsigned int %s[NR_FREQ * NR_MT_CPU_DVFS][ARRAY_COL_SIZE] = {\n"
            "\t/* Freq, Vproc, post_div, clk_div */\n"
            "\n\t/* L */\n%s\n"
            "\n\t/* B */\n%s\n"
            "\n\t/* CCI */\n%s\n};" % (table, fmt(LITTLE), fmt(BIG), fmt(CCI)))


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    for name, tbl in (("LITTLE", LITTLE), ("BIG", BIG), ("CCI", CCI)):
        assert len(tbl) == 16, (name, len(tbl))
        assert all(tbl[i][0] > tbl[i + 1][0] for i in range(15)), name
    path = root / PVT
    text = path.read_text(encoding="utf-8", newline="")
    for table in ("proTbl_v7", "proTbl"):
        pat = r"static unsigned int %s\[[^\]]+\]\[[^\]]+\] = \{[^\n]*\n.*?\n\};" % table
        if not re.search(pat, text, re.S):
            raise SystemExit("%s not found" % table)
        text = re.sub(pat, lambda _: render(table), text, count=1, flags=re.S)
        print("%s: L %d..%d, B %d..%d, CCI %d..%d"
              % (table, LITTLE[0][0], LITTLE[-1][0], BIG[0][0], BIG[-1][0], CCI[0][0], CCI[-1][0]))
    path.write_text(text, encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
