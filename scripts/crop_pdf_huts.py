from PIL import Image

# Crop bottom area of page 3 where Regensburger Hütte is
im3 = Image.open('state/maps/inspect_huts/pdf_page3_stage2.png')
w, h = im3.size
# Regensburger is near the southern part of Stage 2 map
crop3 = im3.crop((int(w * 0.45), int(h * 0.55), int(w * 0.95), int(h * 0.85)))
crop3.save('state/maps/inspect_huts/pdf_stage2_regensburger_crop.png')

# Crop Page 4 around top (Regensburger) and bottom (Dresdner)
im4 = Image.open('state/maps/inspect_huts/pdf_page4_stage3.png')
w4, h4 = im4.size
# Top part of Stage 3
crop4_top = im4.crop((int(w4 * 0.5), int(h4 * 0.15), int(w4 * 0.95), int(h4 * 0.45)))
crop4_top.save('state/maps/inspect_huts/pdf_stage3_regensburger_crop.png')

# Bottom part of Stage 3 (Dresdner)
crop4_bot = im4.crop((int(w4 * 0.25), int(h4 * 0.55), int(w4 * 0.75), int(h4 * 0.85)))
crop4_bot.save('state/maps/inspect_huts/pdf_stage3_dresdner_crop.png')

print("Saved detailed PDF crops!")
