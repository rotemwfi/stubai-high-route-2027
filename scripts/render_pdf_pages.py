import fitz

doc = fitz.open('state/maps/Stubai_High_Route_Complete_Map_Book_Verified.pdf')
# Page 3 is Stage 2 (ends at Regensburger Hütte)
# Page 4 is Stage 3 (starts at Regensburger Hütte, ends at Dresdner Hütte)
pix3 = doc[2].get_pixmap(dpi=150)
pix3.save('state/maps/inspect_huts/pdf_page3_stage2.png')

pix4 = doc[3].get_pixmap(dpi=150)
pix4.save('state/maps/inspect_huts/pdf_page4_stage3.png')

print("Saved PDF page renderings!")
