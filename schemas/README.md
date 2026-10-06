# Export conventions

`results.json` is UTF-8, strict JSON (no NaN/Infinity numeric tokens).
Undefined correlation/SSIM values are null. Infinite PSNR is the string "Infinity".

- metadata: protocol, platform, processor, Python, libraries, backend and timing clock.
- image_id, shape, image_sha256: provenance of the decoded uint8 image.
- nonce_hex: public 16-byte nonce; lut: 16 integers; seed: experiment RNG seed.
- statistics: three rows, Original/R1/R2.
- differential_trials: one row per plaintext perturbation per round.
- key_trials_raw: one row per changed key bit.
- runtime_raw: per-repetition encrypt_ms and decrypt_ms.
- runtime: medians, sample standard deviations, decimal MB/s, warm-ups, repetitions,
  and round_material_included=false.
- recovery and cipher_difference: image-pair metrics.

There is no secret key field. Raw trials are never replaced by manuscript values.
Ciphertext format and KDF are defined in docs/PROTOCOL.md.
