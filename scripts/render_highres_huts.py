from PIL import Image
from inspect_huts_on_tiles import render_crop

# High resolution 0.8 m/pixel zoom 15 crop around Dresdner Hütte
crop_dres = render_crop(662663, 5207172, half_span=160, res=0.8, zoom=15)
crop_dres.save('state/maps/inspect_huts/dresdner_highres.png')

# High resolution crop around Regensburger Hütte
crop_reg = render_crop(666956, 5213587, half_span=160, res=0.8, zoom=15)
crop_reg.save('state/maps/inspect_huts/regensburger_highres.png')

# High resolution crop around Franz-Senn
crop_fs = render_crop(664611, 5216908, half_span=160, res=0.8, zoom=15)
crop_fs.save('state/maps/inspect_huts/franz_senn_highres.png')

# High resolution crop around Sulzenau
crop_sulz = render_crop(665888, 5207011, half_span=160, res=0.8, zoom=15)
crop_sulz.save('state/maps/inspect_huts/sulzenau_highres.png')

print("Highres crops rendered!")
