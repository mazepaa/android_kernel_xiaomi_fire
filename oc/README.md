# inferno-oc — overclock branch (Xiaomi Redmi A3 «fire», MT6768 / MT6769H)

Base: `deryardi73/android_kernel_xiaomi_fire@inferno-new` (`21b15644`).

## What the live device says (root, `/proc`)

```
MT_CPU_DVFS_LL  2100000 108625 | 1800000 98625 | 1625000 91125 | ... | 500000 63000
MT_CPU_DVFS_L   2300000 112625 | 2050000 109750 | 1900000 104250 | ... | 500000 63000
MT_CPU_DVFS_CCI 1477000 104125 | 1263000 98750 | 1049000 85500 | ... | 500000 63000
dvfsp change_flag = 0   (DTS tables NOT applied)
/proc/gpufreq: [0] 1000000 @ 87500 -- stock top is 1.0 GHz, already 87.5 mV higher
               than the 95 mV in the header, g_segment_id = 5
```

That ladder is **proTbl / proTbl_v7** (`CPU_LEVEL_2`), not `FY_G75Tbl` and not
`FY_6768Tbl`. So this branch patches `proTbl` + `proTbl_v7`.

## What is changed

| File | Change |
|---|---|
| `drivers/gpu/mediatek/gpufreq/mt6768/mtk_gpufreq_core.h` | GPU top OPP **1 150 000 kHz @ 100 000 (1 000 mV)**; VSRAM chain shifted one slot so every existing step keeps its voltage |
| `mtk_cpufreq_opp_pv_table.h` → `proTbl` and `proTbl_v7` | 16-slot ladders: little `1800 … 1230 … 1111 … 350`, big `2300, 2202, 2050, 1900, 1850, 1800, … 350`, CCI `1477 … 350` |
| `drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_main.c` | log-only helper: prints when an OPP hits the `MAX_VPROC_VOLT` (1120 mV) ceiling. **Cap not raised.** |

`NR_FREQ` is 16 — the SSPM/MCUPM PVT copy loop takes exactly 16 OPPs, so the
350 MHz floor replaces the lowest slot rather than adding a 17th.

## Build

`.github/workflows/build-oc.yml` → Actions → *Build inferno-oc kernel* →
**Run workflow**. Artifacts: `Image.gz` (and `Image.gz-dtb` / `dtb.img` if the
tree produces them). The workflow is a starting point — check the toolchain
step before using it.

