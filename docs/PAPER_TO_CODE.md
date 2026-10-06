# Paper-to-code map

| Manuscript process | Implementation | Verification / scope |
|---|---|---|
| Nonlinear Boolean core G | core.CORE_TERMS, core.core | All 16 values generated from ANF, not a seed LUT |
| S = B G(Ax XOR alpha) XOR beta | core.construct, core.trace | Binary/invertibility validation; every intermediate value shown |
| Inverse S-box | core.inverse | Exact permutation inverse and round-trip identities |
| NL / Walsh LAT | core.analyze | All 15 component masks, 16 input masks; independent reference test |
| Differential uniformity / DDT | core.analyze | Exhaustive 16×16 differences |
| Forward/inverse SAC | core.analyze | All 16 bit-pair entries |
| ANF / degree / term count | core.anf | Möbius transform; exhaustive reconstruction tests |
| FP / OFP | core.analyze | Exhaustive x and x XOR F comparisons |
| BIC-NL / BIC-SAC | core.analyze | Pairwise coordinate XOR conventions documented |
| 25 benchmark LUTs | sboxlab/data/benchmarks.json | Transcribed from supplied manuscript; metrics recalculated |
| 28-gate networks | circuits.simulate | All inputs; counts, dependency depth, Boolean outputs |
| Circuit visuals | assets, circuits.dot | Original manuscript diagrams plus labeled dependency graph |
| Automatic logic synthesis | circuits.run_abc | Optional new baseline; original search scripts unavailable |
| Affine-class exploration | core.affine_search | Reproducible bounded sampling, not exhaustive classification |
| Domain-separated key material | cipher.material | Explicit v1 serialization; original encoding incomplete |
| Nibble substitution | cipher.encrypt/decrypt | Every uint8 uses the same high/low-nibble rule |
| Pixel permutation | cipher.material/encrypt/decrypt | Stable-score permutation, exact inverse |
| Forward/backward diffusion | cipher.diffuse/undiffuse | Independent scalar recurrence tests |
| R1/R2 and recovery | experiments.run | Exact array equality checked |
| Entropy / histogram / chi-square | experiments.stats | Computed from current bytes |
| H/V/D correlations | experiments.stats; export.experiment_zip | All three axes and plots |
| MSE/PSNR/SSIM/recovery | experiments.recovery | Current outputs, no reference-table substitution |
| 100 plaintext / 30 key perturbations | experiments.run | Every raw trial exported |
| 5 warm-ups / 30 timings | experiments.run | Executing machine metadata, actual times only |
| Tables and figures | export | CSV, JSON, LaTeX, PNG, PDF |

No independent literature verification is implied by importing the source catalog.
The bibliography is supplied for traceability. The manuscript's code-availability
statement is not evidence that its original scripts were present in its ZIP.
