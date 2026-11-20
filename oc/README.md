# inferno-oc — overclock branch (Xiaomi Redmi A3 «fire», MT6768 / MT6769H)

Base: `deryardi73/android_kernel_xiaomi_fire@inferno-new` (`21b15644`).

## What is changed

| File | Change |
|---|---|
| `drivers/gpu/mediatek/gpufreq/mt6768/mtk_gpufreq_core.h` | GPU top OPP **1 150 000 kHz @ 100 000 (1 000 mV)**; VSRAM chain shifted one slot so every existing step keeps its voltage |
| `drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6768/mtk_cpufreq_opp_table.h` | **`FY_G75Tbl`** (CPU_LEVEL_6) — 16-slot ladder: little top 1800, extra steps 1230/1111 MHz, **floor 350 MHz**; big top 2000 with extra steps 2202/2050/1900/1850/1800, floor 350; CCI floor 350 |
| `drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_main.c` | log-only helper: prints when an OPP hits the `MAX_VPROC_VOLT` (1120 mV) ceiling. **Cap not raised** — no voltage change, no behaviour change |
| `arch/arm64/configs/ksu_defconfig` | prepended to the build config by the workflow (KernelSU + SUSFS) |

`NR_FREQ` is 16 in this tree — 16 OPPs per cluster is a hardware/SSPM limit, so
"more steps above 1 GHz" always replaces existing slots, it never adds a 17th.

## Build

`.github/workflows/build-oc.yml` → Actions → *Build inferno-oc kernel* → **Run workflow**
(or push to this branch). Artifacts: `Image.gz`, `Image.gz-dtb` if produced, `dtb.img`.

## Flash

Boot.img / AnyKernel3 is not produced by this branch yet — use the recovery or
`fastboot boot dist/Image` **only after** repacking, because the raw `Image` alone
is not a boot image.

Before flashing check the CPU level the kernel picks:

```
adb shell dumpsys telephony.registry | grep -i sku   # or: getprop ro.boot.hardware.sku
```

Xiaomi fire reports `androidboot.product.hardware.sku=hcesim`. The live DT on the
stock-18-11 kernel shows `dvfsp change_flag = 0`, so the DTS tables are not applied
and the running ladder (2100 / 2300 MHz) does not match `FY_G75Tbl` either — the
`CPU_LEVEL` mapping in `_mt_cpufreq_get_cpu_level()` must be confirmed against the
dump `cat /proc/cpufreq/cpufreq_opp_dump` **with root** before trusting this branch.
