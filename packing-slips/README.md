# Exzmoto packing slips for Shopify

1. Shopify admin → Settings → Shipping and delivery → Packing slips → Edit.
2. Select all the existing code and delete it.
3. Paste the contents of one `.liquid` file here, then Save.
4. Use "Preview template" to check it with a real order.

- `1-clean-pro.liquid` — clean black and white, Letter/A4, saves ink.
- `2-bold-brand.liquid` — dark header and footer with the ad gradient (prints color).
- `3-thermal-4x6.liquid` — 4x6 thermal label printers, black only.

To use your logo image, replace `{{ shop.name | upcase }}` in the logo div with `<img src="YOUR LOGO URL">` (upload it in Content → Files and copy its link).
