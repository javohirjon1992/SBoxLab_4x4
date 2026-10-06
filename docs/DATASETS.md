# Image inputs

The manuscript uses these USC-SIPI image identifiers:

| ID | Name in manuscript | Shape | Mode |
|---|---|---|---|
| 4.1.05 | House | 256 × 256 | RGB |
| 4.2.07 | Peppers | 512 × 512 | RGB |
| 5.1.10 | Aerial | 256 × 256 | Grayscale |
| 5.1.11 | Airplane | 256 × 256 | Grayscale |

Obtain the original images according to their dataset terms and put local copies
in `private_images/`, or upload them through the UI. This repository does not
redistribute those images. Uploaded images are converted to 8-bit L or RGB; there
is no automatic resizing. RGBA alpha is dropped. Record that conversion when comparing
experiments. The report hashes the decoded array, not compressed file bytes.

`examples/synthetic_demo.png` is an independently generated geometric RGB test pattern.
Its results are demonstration measurements, not USC-SIPI manuscript results.
