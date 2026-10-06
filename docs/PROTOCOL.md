# SBoxLab-image-v1

This document resolves serialization details that were not fully specified in the
supplied manuscript. It specifies this implementation, not an inferred original binary format.

## Input and conventions

- Images: row-major `uint8`, either H×W grayscale or H×W×3 RGB.
- RGB pixels retain channel order R,G,B; channels move together during permutation.
- Key: exactly 16 bytes decoded from 32 hexadecimal characters.
- LUT: bijection of 0..15. Bit 0 is the least significant bit.
- Both rounds use the same nibble S-box; round material differs.

## Nonce

Serialize `[image_id, list(image.shape)]` as UTF-8 JSON with `separators=(',', ':')`
and Python's default `ensure_ascii=True`. The nonce is the first 16 bytes of SHA-256.
This deterministic nonce is for reproducible experiments and may repeat for the same
ID/shape. It is not a production nonce-management design.

## Round material

For r=1,2, define:

```text
prefix = ASCII("SBoxLab-image-v1") || 00 || key[16] || nonce[16] || uint32_be(r)
RK = SHA256(prefix || ASCII("RK"))[0:16]
DF = SHA256(prefix || ASCII("DF"))[0:16]
DB = SHA256(prefix || ASCII("DB"))[0:16]
IVF = SHA256(prefix || ASCII("IVF"))[0]
IVB = SHA256(prefix || ASCII("IVB"))[0]
scores = SHAKE256(prefix || ASCII("PERM")), output 8*N bytes
```

Interpret scores as N unsigned 64-bit **little-endian** integers. Stable ascending
argsort gives pi. Equal scores retain input-index order. Inverse pi is argsort(pi).
This is a specified experimental derivation, not a claim of a standardized KDF.

## Round and inverse

1. XOR each byte with RK[i mod 16].
2. Substitute each high/low nibble: `16*S[high] + S[low]`.
3. Permute whole pixels: `P[j] = B[pi[j]]`.
4. Flatten and apply:

```text
F[0] = P[0] XOR DF[0] XOR IVF
F[i] = P[i] XOR DF[i mod 16] XOR ROTL8(F[i-1],1)
X[L-1] = F[L-1] XOR DB[(L-1) mod 16] XOR IVB
X[i] = F[i] XOR DB[i mod 16] XOR ROTR8(X[i+1],1)
```

The inverse obtains F from X, then P from F using the same XOR relations, then
applies inverse pixel permutation, inverse nibble substitution, and round-key XOR.
Rounds are inverted in order 2,1.

## Vectorized diffusion

For a recurrence `y[i] = q[i] XOR ROTL8(y[i-1], step)`, absorb the IV into q[0].
Define `z[i] = ROTL8(q[i], -i*step)`. Then:

```text
y[i] = ROTL8(cumulative_XOR(z)[i], i*step)
```

The backward recurrence is the same construction on the reversed sequence with
`step=-1`. NumPy implements the cumulative XOR; scalar-reference tests check this
identity for multiple lengths and both image modes. Temporary arrays use O(L)
space; no Numba JIT timings are being implied.

## Statistics

- Entropy and histogram: over all bytes (RGB channels pooled).
- Correlation: adjacent horizontal, vertical, diagonal pixel pairs, same channel;
  flatten pair arrays after spatial pairing. Undefined constant/tiny cases are null.
- NPCR: percentage of changed bytes, including RGB components separately.
- UACI: mean absolute byte difference / 255 × 100.
- Hamming: percentage of changed ciphertext bits.
- Expected independent byte reference: NPCR 99.609375%; UACI 100×257/(3×256)%.
- Plaintext trials: one bit selected with replacement using NumPy default_rng(seed).
- Key trials: distinct key positions without replacement, after plaintext RNG draws.
- Same nonce and image ID are retained for all sensitivity perturbations.
- SSIM uses scikit-image defaults, data_range=255, channel_axis=-1 for RGB and
  an odd window up to 7. Images smaller than 3 pixels in either dimension return null.
- Chi-square p-values are descriptive; small expected bin counts limit asymptotic interpretation.

## Timing

Use perf_counter_ns, 5 untimed warm-ups, and 30 repetitions by default. Only
complete two-round encrypt/decrypt calls are timed. KDF, image input, verification,
statistics, and figure generation are excluded. Report median, sample standard
deviation and decimal MB/s = bytes/(1000 × median milliseconds).

## Cipher bundle

NPZ fields: cipher, nonce (16 uint8 bytes), lut, image_id, protocol. Loading uses
allow_pickle=False and a 64 MB decompressed-size limit. The key is never saved.
There is no authentication, corruption-detection, or wrong-key guarantee.
