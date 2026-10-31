from PIL import Image

# Crop Regensburger area on Page 3 (Stage 2)
im3 = Image.open('state/maps/inspect_huts/final_stage2_crop.png')
w3, h3 = im3.size
crop_reg = im3.crop((int(w3 * 0.45), int(h3 * 0.55), int(w3 * 0.95), int(h3 * 0.82)))
crop_reg.save('state/maps/inspect_huts/verify_regensburger_circle.png')

# Crop Dresdner area on Page 4 (Stage 3)
im4 = Image.open('state/maps/inspect_huts/final_stage3_crop.png')
w4, h4 = im4.size
crop_dres = im4.crop((int(w4 * 0.28), int(h4 * 0.58), int(w4 * 0.72), int(h4 * 0.82)))
crop_dres.save('state/maps/inspect_huts/verify_dresdner_circle.png')

print("Saved verification crops!")
