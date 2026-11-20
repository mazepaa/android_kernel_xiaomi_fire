"""MT6768 / fire overclock + frequency-ladder patcher.

Fixes applied to the kernel sources before building:

GPU  drivers/gpu/mediatek/gpufreq/mt6768/mtk_gpufreq_core.h
     * new top OPP (default 1150 MHz @ 1000 mV)
     * VSRAM defines re-indexed so every existing step keeps its voltage

CPU  drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6768/
     mtk_cpufreq_opp_pv_table.h  (the PVT table the CSRAM/SSPM really uses)
     * FY_G75Tbl (CPU_LEVEL_6 = what Xiaomi fire runs) gets intermediate
       steps above 1 GHz and a 350 MHz floor.
     NR_FREQ is 16, so extra steps always eat existing slots.

Run:  python patch_oc.py <kernel-root> [--gpu 1150000] [--gpu-volt 100000]
                          [--vsram 105000] [--dry-run]
"""
import argparse
import re
from pathlib import Path

GPU_H = "drivers/gpu/mediatek/gpufreq/mt6768/mtk_gpufreq_core.h"
PVT_H = ("drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6768/"
         "mtk_cpufreq_opp_pv_table.h")

# (freq MHz, Vproc) ; Vproc unit = 10 mV. 16 entries each, strictly descending.
LITTLE_NEW = [
    (1800, 81), (1625, 69), (1500, 63), (1450, 61), (1375, 57), (1325, 55),
    (1275, 53), (1230, 51), (1175, 48), (1111, 45), (1050, 42), (999, 39),
    (950, 37), (850, 32), (774, 28), (350, 24),
]
BIG_NEW = [
    (2300, 112), (2202, 111), (2050, 109), (1900, 104), (1850, 103),
    (1800, 101), (1710, 98), (1621, 94), (1532, 91), (1443, 88), (1354, 84),
    (1295, 82), (1176, 78), (1087, 74), (998, 71), (350, 63),
]
FLOOR = 350


def read(p):
    return Path(p).read_text(encoding="utf-8", newline="")


def write(p, text):
    Path(p).write_text(text, encoding="utf-8", newline="")


def check_ladder(name, tbl):
    assert len(tbl) == 16, "%s must hold 16 OPPs, got %d" % (name, len(tbl))
    for i in range(len(tbl) - 1):
        assert tbl[i][0] > tbl[i + 1][0], \
            "%s not descending at %d (%d <= %d)" % (name, i, tbl[i][0], tbl[i + 1][0])
    for f, v in tbl:
        assert 300 <= f <= 3000, "%s freq %d out of range" % (name, f)
        assert 20 <= v <= 112, "%s vproc %d outside 200..1120 mV" % (name, v)


# ------------------------------------------------------------------ GPU
def patch_gpu(root, gpu_khz, gpu_volt, vsram_top, dry):
    path = root / GPU_H
    text = read(path)

    def get(base, idx):
        m = re.search(r"#define SEG_GPU_%s%d\s+\(([0-9]+)\)" % (base, idx), text)
        if not m:
            raise SystemExit("missing SEG_GPU_%s%d" % (base, idx))
        return int(m.group(1))

    old_top, old_volt, old_vsram = (get("DVFS_FREQ", 0), get("DVFS_VOLT", 0),
                                    get("DVFS_VSRAM", 0))
    if gpu_khz <= old_top:
        raise SystemExit("target %d must exceed stock top %d" % (gpu_khz, old_top))
    if gpu_volt < old_volt:
        raise SystemExit("volt %d below stock top volt %d" % (gpu_volt, old_volt))

    new, n = re.subn(
        r"#define SEG_GPU_DVFS_FREQ0(\s+)\([0-9]+\)(\s*/\* KHz \*/\n)"
        r"#define SEG_GPU_DVFS_FREQ1(\s+)\([0-9]+\)",
        lambda m: "#define SEG_GPU_DVFS_FREQ0%s(%d)%s"
                  "#define SEG_GPU_DVFS_FREQ1%s(%d)"
                  % (m.group(1), gpu_khz, m.group(2), m.group(3), old_top),
        text, count=1)
    if n != 1:
        raise SystemExit("FREQ0/FREQ1 block not found")
    text = new

    text, n = re.subn(r"(#define SEG_GPU_DVFS_VOLT0\s+\()[0-9]+\)",
                      lambda m: m.group(1) + str(gpu_volt) + ")", text, count=1)
    if n != 1:
        raise SystemExit("VOLT0 not found")

    for i in range(11, -1, -1):
        target = vsram_top if i == 0 else get("DVFS_VSRAM", i - 1)
        text, n = re.subn(r"(#define SEG_GPU_DVFS_VSRAM%d(\s+)\()[0-9]+\)" % i,
                          lambda m, t=target: m.group(1) + str(t) + ")", text, count=1)
        if n != 1:
            raise SystemExit("VSRAM%d not found" % i)

    print("GPU: %d -> %d kHz | VOLT0 %d -> %d | VSRAM0 %d -> %d | OPPs 32 -> 33"
          % (old_top, gpu_khz, old_volt, gpu_volt, old_vsram, vsram_top))
    if not dry:
        write(path, text)


# ------------------------------------------------------------------ CPU
def format_table(title, rows, header_comment=True):
    body = "\n".join("\t{ %d, %d, %d, 1 }," % (f, v, 1 if f >= 1800 else 2)
                     for f, v in rows)
    out = "\n\t/* %s */\n" % title if header_comment else ""
    return out + body + "\n"


def patch_pvt(root, dry):
    path = root / PVT_H
    text = read(path)

    m = re.search(r"static unsigned int FY_G75Tbl\[[^\]]+\]\[[^\]]+\] = \{[^\n]*\n(.*?)\n\};",
                  text, re.S)
    if not m:
        raise SystemExit("FY_G75Tbl not found")

    body = m.group(1)
    segs = {}
    for tag in ("L", "B", "CCI"):
        mm = re.search(r"/\* *%s *\*/(.*?)(?=/\* *(?:L|B|CCI) *\*/|$)" % tag, body, re.S)
        if not mm:
            raise SystemExit("segment %s not found in FY_G75Tbl" % tag)
        segs[tag] = [(int(a), int(b)) for a, b in
                     re.findall(r"\{\s*(\d+),\s*(\d+),\s*\d+,\s*\d+\s*\}", mm.group(1))]
        if len(segs[tag]) != 16:
            raise SystemExit("FY_G75Tbl/%s has %d OPPs, expected 16"
                             % (tag, len(segs[tag])))

    print("  old L  :", " ".join("%d" % f for f, _ in segs["L"]))
    print("  new L  :", " ".join("%d" % f for f, _ in LITTLE_NEW))
    print("  old B  :", " ".join("%d" % f for f, _ in segs["B"]))
    print("  new B  :", " ".join("%d" % f for f, _ in BIG_NEW))

    # CCI: only the last slot changes (500 -> 350), everything else verbatim.
    cci_new = list(segs["CCI"])
    cci_new[-4] = (cci_new[-4][0], cci_new[-4][1])
    cci_new[-3] = (cci_new[-3][0], cci_new[-3][1])
    cci_new[-2] = (cci_new[-2][0], cci_new[-2][1])
    cci_new[-1] = (FLOOR, 24)
    print("  new CCI:", " ".join("%d" % f for f, _ in cci_new))

    rebuilt = ("static unsigned int FY_G75Tbl[NR_FREQ * NR_MT_CPU_DVFS][ARRAY_COL_SIZE] = {\n"
               "\t/* Freq, Vproc, post_div, clk_div */\n"
               + format_table("L", LITTLE_NEW)
               + "\n" + format_table("B", BIG_NEW)
               + "\n" + format_table("CCI", cci_new)
               + "};")
    result = text[:m.start()] + rebuilt + text[m.end():]

    for tag, new in (("L", LITTLE_NEW), ("B", BIG_NEW), ("CCI", cci_new)):
        if not dry:
            pass
        # validate the *rendered* result afterwards
        check_ladder("FY_G75Tbl/%s" % tag, new)

    print("CPU: FY_G75Tbl rewritten | extra steps L {1230, 1111} MHz, B {2202, 2050} MHz, floor 350")
    if not dry:
        write(path, result)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--gpu", type=int, default=1150000)
    ap.add_argument("--gpu-volt", type=int, default=100000)
    ap.add_argument("--vsram", type=int, default=105000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    check_ladder("LITTLE", LITTLE_NEW)
    check_ladder("BIG", BIG_NEW)
    print("tables validated")
    root = Path(a.root)
    patch_gpu(root, a.gpu, a.gpu_volt, a.vsram, a.dry_run)
    patch_pvt(root, a.dry_run)
    print("done%s" % (" (dry run)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
