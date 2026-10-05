# Exzmoto Ultra Bee ad

- `exzmoto-ultra-bee-ad.mp4` — rendered 30 s vertical ad
- `exzmoto-bracket-black.glb` / `-silver.glb` — 3D bracket models
- Rebuild: serve this folder (`npx http-server -p 8123 .`), run `node render.js <shard> <nShards> 30 900` per shard, then encode `frames/f%04d.jpg` with ffmpeg.
- The 3D model is the photo silhouette (outline + holes) extruded 0.075 image-widths, with the photo as the front texture and chrome ear collars. Thickness is an estimate, not measured.
