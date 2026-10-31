import xml.etree.ElementTree as ET

tree = ET.parse("export.gpx")
root = tree.getroot()
pts = [(float(p.attrib["lat"]), float(p.attrib["lon"]), float(p.find("{*}ele").text if p.find("{*}ele") is not None else 0)) for p in root.findall(".//{*}trkpt")]

print(f"Points 0 to 20:")
for i in [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]:
    print(f"pt {i:4d}: lat={pts[i][0]:.5f}, lon={pts[i][1]:.5f}, ele={pts[i][2]}m")
