from pathlib import Path
from inspect_huts_on_tiles import render_crop

out_dir = Path("state/maps/inspect_huts")
# Let's search east of 666956 for Regensburger Hütte text/symbol
crop_wide = render_crop(667300, 5213000, half_span=500, res=2.0, zoom=15)
crop_wide.save(out_dir / "regensburger_wide.png")

# And search wider around Dresdner Hütte
crop_dres = render_crop(662800, 5207100, half_span=500, res=2.0, zoom=15)
crop_dres.save(out_dir / "dresdner_wide.png")
print("Saved wide crops!")
