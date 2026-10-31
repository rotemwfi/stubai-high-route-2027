from inspect_huts_on_tiles import render_crop
from pathlib import Path

out_dir = Path("state/maps/inspect_huts")
# Let's inspect along Falbesoner Bach down to Falbeson / Ranalt
for n_target in [5213000, 5212500, 5212000, 5211500]:
    crop = render_crop(667000, n_target, half_span=400, res=2.0, zoom=15)
    crop.save(out_dir / f"scan_n_{n_target}.png")
print("Saved scan crops!")
