#!/usr/bin/env python3
"""Patch mtk_cpufreq_main.c so OPP voltages above 1120 mV are not silently clamped.

The stock code does `volt = MIN(volt, MAX_VPROC_VOLT)` (SUPPORT_VOLT_HW_AUTO_TRACK),
which quietly flattens every OPP on or above the 1120 mV line (the current
2300 MHz step at 1126.25 mV already runs flattened).

Usage: python patch_volt_cap.py <kernel-root> [--cap 115000]
"""
import argparse
import re
from pathlib import Path

MAIN_C = ("drivers/misc/mediatek/base/power/cpufreq_v1/src/"
          "mtk_cpufreq_main.c")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--cap", type=int, default=115000)
    a = ap.parse_args()

    path = Path(a.root) / MAIN_C
    text = path.read_text(encoding="utf-8", newline="")
    pat = r"(\n\s*)(volt = MIN\(volt, MAX_VPROC_VOLT\);)"
    new, n = re.subn(pat, r"\1\2\1vf_volt_cap_note(__LINE__, volt);", text, count=1)
    if n != 1:
        raise SystemExit("clamp line not found - tree already patched?")

    helper = (
        "\n#ifdef SUPPORT_VOLT_HW_AUTO_TRACK\n"
        "/* OC: log when an OPP exceeds the PMIC ceiling instead of staying silent */\n"
        "static inline void vf_volt_cap_note(int line, unsigned int volt)\n"
        "{\n"
        "\tif (volt >= %d)\n"
        "\t\ttag_pr_info(\"@%%s():%%d volt %%d uV is capped to MAX_VPROC_VOLT\\n\",\n"
        "\t\t\t__func__, line, volt * 10);\n"
        "}\n"
        "#endif\n\n" % a.cap
    )
    anchor = "#define DCM_ENABLE 1"
    if anchor not in new:
        raise SystemExit("anchor DCM_ENABLE not found")
    idx = new.index(anchor)
    idx = new.rindex("\n", 0, idx) + 1
    new = new[:idx] + helper + new[idx:]

    path.write_text(new, encoding="utf-8", newline="")
    print("patched %s (log-only, cap stays %d)" % (MAIN_C, a.cap))


if __name__ == "__main__":
    main()
