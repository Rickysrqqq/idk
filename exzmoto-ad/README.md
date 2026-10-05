# Exzmoto Ultra Bee ad

- `exzmoto-ultra-bee-ad.mp4` — rendered 30 s vertical ad
- `exzmoto-bracket-black.glb` / `-silver.glb` — 3D bracket models
- Rebuild: serve this folder (`npx http-server -p 8123 .`), run `node render.js <shard> <nShards> 30 900` per shard, then encode `frames/f%04d.jpg` with ffmpeg.
- The 3D model is the photo silhouette (outline + holes) extruded 15 mm (assumes the bracket is ~120 mm wide), with the photo as the front texture and chrome ear collars. Thickness is an estimate, not measured.

- Ad scenes 4-6 use a 3D build: 15 mm bracket stacked on a 3 mm rotor guard plate (guard thickness assumed). Scale is estimated from the ~220 mm rotor; edit `MM` in `lib/bracket.js` if the real bracket width differs.
