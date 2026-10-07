# Grok prompt — enhance the Exzmoto ad (video-to-video upgrade)

Use this when you give Grok the finished ad clips and want the SAME video, just higher quality. Grok's limit is 15 s per clip, so use the three clips in `grok-clips/` (12.5 s, 13 s, 10 s). Attach the matching clip plus the 4 reference photos in `grok-refs/` to each run.

```
Enhance and upgrade the attached video to a higher-quality, cinematic commercial grade. This is a quality pass, not a redesign: keep the exact same layout, timing, motion, camera moves, colors, headlines, text, pills, UI cards, cursor taps, transitions and audio. Do not add, remove or reword any text. Do not change the order or length of the shots.

Use the attached reference photos only as the ground truth for how the real products look (the silver bracket + rotor guard, the black anodized bracket, the chrome rotor guard with the EXZMOTO engraving, and the SurRon HT caliper). Wherever those parts appear in the video, rebuild their detail from the photos: crisp machined edges, accurate CNC toolpath texture, sharp EXZMOTO engraving, true polished-chrome reflections, correct black anodized finish, and the real caliper casting and markings. Do not redesign, recolor or reshape any part.

Quality target: native 4K look, razor-sharp edges, clean text with no blur or shimmer, no compression artifacts or banding, smooth gradients in the dark violet/blue backgrounds, rich blacks, realistic specular highlights and glints on the chrome, soft cinematic glow, subtle film grain, stable 24–60 fps motion with no flicker or warping. Premium high-contrast product-commercial grade. No people, no watermarks, no new objects.
```

Tips
- If Grok changes text or timing, add: "Treat the input video as locked. Only improve image quality."
- Run the three clips separately, then join them in an editor (the cuts are at scene changes, so they join cleanly).
- If it garbles small text, enhance without it and re-add the headlines/pills in an editor, or use a dedicated video upscaler (Topaz Video AI, etc.) for the final 4K pass.
