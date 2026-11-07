(function() {
  proj4.defs("EPSG:32632", "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs");

  let data = window.ROUTE_3D_DATA;
  let track = data.track || [];
  let waypoints = data.waypoints || [];

  const urlParams = new URLSearchParams(window.location.search);
  let mapboxToken = urlParams.get("mapbox_token") || localStorage.getItem("AGY_MAPBOX_TOKEN") || data.default_keys.mapbox_token || "";
  let googleKey = urlParams.get("google_key") || localStorage.getItem("AGY_GOOGLE_3D_KEY") || data.default_keys.google_key || "";

  let map = null;
  let cesiumViewer = null;
  let isPlaying = false;
  let animFrame = null;
  let playProgress = 0; // 0 .. track.length - 1
  let currentBearer = 0;
  let lockedBearing = null;
  let targetBearing = 0;
  let isBearingLocked = false;
  let currentValleyBias = 0;
  let targetValleyBias = 0;
  let currentPitch = 65;
  let targetPitch = 65;
  let isInitialFrame = true;
  let markerCursor = null;

  const titleEl = document.getElementById("route-title");
  const statsEl = document.getElementById("route-stats");
  const hudDist = document.getElementById("hud-dist");
  const hudEle = document.getElementById("hud-ele");
  const hudUtm = document.getElementById("hud-utm");
  const hudCam = document.getElementById("hud-cam");
  const scrubber = document.getElementById("route-scrubber");
  const elevCanvas = document.getElementById("elev-canvas");
  const playBtn = document.getElementById("btn-play");
  const zoomSlider = document.getElementById("zoom-slider");
  let currentZoom = 14.0;
  const pitchSlider = document.getElementById("pitch-slider");
  const exagSlider = document.getElementById("exag-slider");
  const speedSelect = document.getElementById("speed-select");
  const engineSelect = document.getElementById("engine-select");

  function updateHeader() {
    titleEl.textContent = data.title || "3D Route Fly-Through";
    const s = data.stats;
    statsEl.textContent = `${s.total_distance_km} km | +${s.total_ascent_m}m / -${s.total_descent_m}m | ${s.min_ele_m}m–${s.max_ele_m}m`;
    scrubber.max = Math.max(1, track.length - 1);
    drawElevationProfile(0);
  }

  function computeBearing(lat1, lon1, lat2, lon2) {
    const toRad = d => d * Math.PI / 180;
    const toDeg = r => r * 180 / Math.PI;
    const dLon = toRad(lon2 - lon1);
    const y = Math.sin(dLon) * Math.cos(toRad(lat2));
    const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
              Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }

  function updateHUD(idx) {
    const pt = typeof getPointAtIdx === "function" ? getPointAtIdx(idx) : track[Math.min(track.length - 1, Math.max(0, Math.floor(idx)))];
    if (!pt) return;
    hudDist.textContent = `${pt.dist_km.toFixed(2)} km`;
    hudEle.textContent = `${Math.round(pt.ele)} m`;
    try {
      const [e, n] = proj4("EPSG:4326", "EPSG:32632", [pt.lon, pt.lat]);
      hudUtm.textContent = `${Math.round(e)}E ${Math.round(n)}N`;
    } catch (_) {}
    const isAutoPitch = Math.abs(currentPitch - parseFloat(pitchSlider.value)) > 2.5;
    const lockLabel = isBearingLocked ? "🔒 locked" : "↻ turning";
    hudCam.textContent = `${Math.round(currentPitch)}°${isAutoPitch ? " (auto)" : ""} | ${Math.round(currentBearer)}° ${lockLabel} | Z:${currentZoom.toFixed(1)} | ${exagSlider.value}x`;
  }

  function drawElevationProfile(activeIdx) {
    const ctx = elevCanvas.getContext("2d");
    const w = elevCanvas.width;
    const h = elevCanvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!track.length) return;

    const minE = data.stats.min_ele_m - 80;
    const maxE = data.stats.max_ele_m + 80;
    const spanE = Math.max(100, maxE - minE);

    ctx.beginPath();
    ctx.moveTo(0, h);
    track.forEach((p, i) => {
      const x = (i / (track.length - 1)) * w;
      const y = h - ((p.ele - minE) / spanE) * (h - 10) - 4;
      ctx.lineTo(x, y);
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fillStyle = "rgba(56, 189, 248, 0.22)";
    ctx.fill();

    ctx.beginPath();
    track.forEach((p, i) => {
      const x = (i / (track.length - 1)) * w;
      const y = h - ((p.ele - minE) / spanE) * (h - 10) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Active cursor line
    const cx = (activeIdx / Math.max(1, track.length - 1)) * w;
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }

  function getRouteGeoJSON() {
    return {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: track.map(p => [p.lon, p.lat, p.ele])
      }
    };
  }

  function buildFree3DStyle(mode) {
    const rasterUrl = mode === "topo3d"
      ? "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
      : "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
    return {
      version: 8,
      sources: {
        rasterBase: {
          type: "raster",
          tiles: [rasterUrl],
          tileSize: 256,
          maxzoom: 17
        },
        terrainDem: {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          encoding: "terrarium",
          maxzoom: 14
        },
        hillshadeDem: {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          encoding: "terrarium",
          maxzoom: 14
        }
      },
      terrain: {
        source: "terrainDem",
        exaggeration: parseFloat(exagSlider.value)
      },
      layers: [
        { id: "base-layer", type: "raster", source: "rasterBase" },
        {
          id: "hills",
          type: "hillshade",
          source: "hillshadeDem",
          paint: { "hillshade-exaggeration": 0.45 }
        }
      ]
    };
  }

  function addRouteAndWaypointsToGL(glMap, libObj) {
    glMap.addSource("route", {
      type: "geojson",
      data: getRouteGeoJSON()
    });
    glMap.addLayer({
      id: "route-casing",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 8 }
    });
    glMap.addLayer({
      id: "route-line",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#dc2626", "line-width": 5 }
    });

    waypoints.forEach(w => {
      const el = document.createElement("div");
      el.className = "hut-marker";
      el.textContent = w.night ? `Night ${w.night}: ${w.name}` : w.name;
      new libObj.Marker({ element: el, anchor: "bottom" })
        .setLngLat([w.lon, w.lat])
        .setPopup(new libObj.Popup().setHTML(`<strong>${w.name}</strong><br/>${w.desc || ""}`))
        .addTo(glMap);
    });

    const curEl = document.createElement("div");
    curEl.style.width = "16px";
    curEl.style.height = "16px";
    curEl.style.borderRadius = "50%";
    curEl.style.background = "#38bdf8";
    curEl.style.border = "3px solid #fff";
    curEl.style.boxShadow = "0 0 12px #38bdf8";
    markerCursor = new libObj.Marker({ element: curEl })
      .setLngLat([track[0].lon, track[0].lat])
      .addTo(glMap);
  }

  function initMapEngine(mode) {
    stopFlythrough();
    const mapDiv = document.getElementById("map3d");
    const cesDiv = document.getElementById("cesium3d");

    if (map) { map.remove(); map = null; }
    if (cesiumViewer) { cesiumViewer.destroy(); cesiumViewer = null; }

    if (mode === "google3d") {
      if (!googleKey) {
        document.getElementById("key-modal").classList.remove("hidden");
        engineSelect.value = "terrain3d";
        return initMapEngine("terrain3d");
      }
      mapDiv.style.display = "none";
      cesDiv.style.display = "block";
      initGoogle3DTiles();
      return;
    }

    mapDiv.style.display = "block";
    cesDiv.style.display = "none";

    if (mode === "mapbox3d") {
      if (!mapboxToken) {
        document.getElementById("key-modal").classList.remove("hidden");
        engineSelect.value = "terrain3d";
        return initMapEngine("terrain3d");
      }
      mapboxgl.accessToken = mapboxToken;
      map = new mapboxgl.Map({
        container: "map3d",
        style: "mapbox://styles/mapbox/satellite-streets-v12",
        center: [track[0].lon, track[0].lat],
        zoom: currentZoom,
        pitch: parseFloat(pitchSlider.value),
        bearing: 160,
        antialias: true
      });
      map.on("wheel", () => {
        setTimeout(() => {
          if (map) {
            currentZoom = parseFloat(map.getZoom().toFixed(1));
            if (zoomSlider) zoomSlider.value = currentZoom;
            updateHUD(playProgress);
          }
        }, 60);
      });
      map.on("style.load", () => {
        map.addSource("mapbox-dem", {
          type: "raster-dem",
          url: "mapbox://mapbox.mapbox-terrain-dem-v1",
          tileSize: 512,
          maxzoom: 14
        });
        map.setTerrain({ source: "mapbox-dem", exaggeration: parseFloat(exagSlider.value) });
        map.addLayer({
          id: "sky",
          type: "sky",
          paint: { "sky-type": "atmosphere", "sky-atmosphere-sun": [0.0, 0.0], "sky-atmosphere-sun-intensity": 15 }
        });
        addRouteAndWaypointsToGL(map, mapboxgl);
      });
      return;
    }

    // Default Keyless 3D Terrain (MapLibre GL v4 + AWS Terrarium DEM)
    map = new maplibregl.Map({
      container: "map3d",
      style: buildFree3DStyle(mode),
      center: [track[0].lon, track[0].lat],
      zoom: currentZoom,
      pitch: parseFloat(pitchSlider.value),
      bearing: 160,
      maxPitch: 82
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("wheel", () => {
      setTimeout(() => {
        if (map) {
          currentZoom = parseFloat(map.getZoom().toFixed(1));
          if (zoomSlider) zoomSlider.value = currentZoom;
          updateHUD(playProgress);
        }
      }, 60);
    });
    map.on("load", () => {
      addRouteAndWaypointsToGL(map, maplibregl);
      updateHUD(0);
    });
  }

  async function initGoogle3DTiles() {
    cesiumViewer = new Cesium.Viewer("cesium3d", {
      imageryProvider: false,
      baseLayerPicker: false,
      geocoder: false,
      timeline: false,
      animation: false
    });
    const tileset = await Cesium.Cesium3DTileset.fromUrl(
      `https://tile.googleapis.com/v1/3dtiles/root.json?key=${encodeURIComponent(googleKey)}`
    );
    cesiumViewer.scene.primitives.add(tileset);
    const positions = Cesium.Cartesian3.fromDegreesArrayHeights(
      track.flatMap(p => [p.lon, p.lat, p.ele + 15])
    );
    cesiumViewer.entities.add({
      polyline: {
        positions,
        width: 6,
        material: Cesium.Color.RED
      }
    });
    cesiumViewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(track[0].lon, track[0].lat - 0.015, track[0].ele + 900),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-30), roll: 0 }
    });
  }

  function getPointAtDistance(dKm) {
    if (!track.length) return null;
    if (dKm <= track[0].dist_km) return track[0];
    const last = track[track.length - 1];
    if (dKm >= last.dist_km) return last;

    let low = 0, high = track.length - 1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (track[mid].dist_km < dKm) low = mid + 1;
      else high = mid - 1;
    }
    const i1 = Math.max(1, Math.min(track.length - 1, low));
    const i0 = i1 - 1;
    const p0 = track[i0];
    const p1 = track[i1];
    const span = p1.dist_km - p0.dist_km;
    const t = span > 0.00001 ? Math.max(0, Math.min(1, (dKm - p0.dist_km) / span)) : 0;
    return {
      lat: p0.lat + (p1.lat - p0.lat) * t,
      lon: p0.lon + (p1.lon - p0.lon) * t,
      ele: p0.ele + (p1.ele - p0.ele) * t,
      dist_km: dKm
    };
  }

  function getPointAtIdx(idxFloat) {
    if (!track.length) return null;
    const i0 = Math.min(track.length - 1, Math.max(0, Math.floor(idxFloat)));
    const i1 = Math.min(track.length - 1, i0 + 1);
    const frac = idxFloat - i0;
    const p0 = track[i0];
    const p1 = track[i1];
    return {
      lat: p0.lat + (p1.lat - p0.lat) * frac,
      lon: p0.lon + (p1.lon - p0.lon) * frac,
      ele: p0.ele + (p1.ele - p0.ele) * frac,
      dist_km: p0.dist_km + (p1.dist_km - p0.dist_km) * frac
    };
  }

  function angleDiff(a, b) {
    return Math.abs(((a - b + 540) % 360) - 180);
  }

  function relativeAngle(targetB, refB) {
    return ((targetB - refB + 540) % 360) - 180;
  }

  function computeCorridorFlight(currPt) {
    const dCurr = currPt.dist_km;
    
    // Macro lookahead point (550m ahead)
    const macroPt = getPointAtDistance(dCurr + 0.550);
    const macroBearing = computeBearing(currPt.lat, currPt.lon, macroPt.lat, macroPt.lon);

    // Mid lookahead point (250m ahead)
    const midPt = getPointAtDistance(dCurr + 0.250);
    const midBearing = computeBearing(currPt.lat, currPt.lon, midPt.lat, midPt.lon);

    // 1. Initialize or Reset
    if (lockedBearing === null || isInitialFrame) {
      lockedBearing = macroBearing;
      currentBearer = lockedBearing;
      targetBearing = lockedBearing;
      isBearingLocked = true;
      isInitialFrame = false;
      return { bearing: currentBearer, pitch: currentPitch };
    }

    // 2. Evaluate triggers to change direction
    const relMacro = angleDiff(macroBearing, lockedBearing);
    const relMid = relativeAngle(midBearing, lockedBearing);
    
    // Cross-track lateral offset in meters (for points in the forward 170-degree arc)
    let crossTrackMeters = 0;
    if (Math.abs(relMid) < 85) {
      crossTrackMeters = Math.abs(250.0 * Math.sin(relMid * Math.PI / 180));
    }

    // Trigger A: Path changed general direction (macro direction changed by > 28 deg)
    const pathChangedDirection = relMacro > 28;

    // Trigger B: Point of view is too far to the side (trail drifted > 150m off center line of sight)
    const pointOfViewTooFarToSide = crossTrackMeters > 150;

    // Trigger C: Terrain blocking the view ahead along lockedBearing
    let terrainBlockingView = false;
    if (map && typeof map.queryTerrainElevation === "function") {
      const radLocked = lockedBearing * Math.PI / 180;
      const probeLat = currPt.lat + (200 * Math.cos(radLocked)) / 111320;
      const probeLon = currPt.lon + (200 * Math.sin(radLocked)) / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eleAhead = map.queryTerrainElevation([probeLon, probeLat]);
      if (eleAhead !== null && eleAhead !== undefined && (eleAhead - currPt.ele) > 95) {
        terrainBlockingView = true;
      }
    }

    if (isBearingLocked) {
      if (pathChangedDirection || pointOfViewTooFarToSide || terrainBlockingView) {
        targetBearing = macroBearing;
        isBearingLocked = false;
      }
    }

    // 3. Update Camera Bearing
    if (isBearingLocked) {
      // KEEP CONSTANT! ZERO fluctuation!
      currentBearer = lockedBearing;
    } else {
      // Smoothly transit toward targetBearing
      const diff = ((targetBearing - currentBearer + 540) % 360) - 180;
      if (Math.abs(diff) < 1.2) {
        currentBearer = targetBearing;
        lockedBearing = targetBearing;
        isBearingLocked = true;
      } else {
        const turnRate = Math.sign(diff) * Math.min(1.2, Math.max(0.15, Math.abs(diff) * 0.10));
        currentBearer = (currentBearer + turnRate + 360) % 360;
      }
    }

    // 4. Slope-Normal & Valley-Side Stand-Off
    let slopeAngleDeg = 0;
    let downhillBearing = 0;
    if (map && typeof map.queryTerrainElevation === "function") {
      const probeR = 120; // 120m terrain sampling radius around point
      const dLat = probeR / 111320;
      const dLon = probeR / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eN = map.queryTerrainElevation([currPt.lon, currPt.lat + dLat]);
      const eS = map.queryTerrainElevation([currPt.lon, currPt.lat - dLat]);
      const eE = map.queryTerrainElevation([currPt.lon + dLon, currPt.lat]);
      const eW = map.queryTerrainElevation([currPt.lon - dLon, currPt.lat]);

      if (eN !== null && eS !== null && eE !== null && eW !== null) {
        const gradX = (eE - eW) / (probeR * 2);
        const gradY = (eN - eS) / (probeR * 2);
        const grade = Math.hypot(gradX, gradY);
        slopeAngleDeg = Math.atan(grade) * 180 / Math.PI;
        downhillBearing = (Math.atan2(-gradX, -gradY) * 180 / Math.PI + 360) % 360;

        // If mountain slope is noticeable (> 6 deg), calculate valley-side stand-off
        if (slopeAngleDeg > 6.0) {
          const relDownhill = relativeAngle(downhillBearing, currentBearer);
          // If downhill is to the left (relDownhill < 0), offset camera eye to left into valley -> bearing turns right (+)
          // If downhill is to the right (relDownhill > 0), offset camera eye to right into valley -> bearing turns left (-)
          const biasStrength = Math.min(1.0, (slopeAngleDeg - 6.0) / 20.0);
          const maxBias = 28.0 * biasStrength;
          targetValleyBias = (relDownhill > 0 ? -1.0 : 1.0) * maxBias;
        } else {
          targetValleyBias = 0;
        }
      }
    } else {
      targetValleyBias = 0;
    }

    // Smooth valley bias so it glides smoothly across gullies
    currentValleyBias += (targetValleyBias - currentValleyBias) * 0.05;
    const effectiveBearing = (currentBearer + currentValleyBias + 360) % 360;

    // 5. Slope-Perpendicular Pitch & Terrain Clearance
    const userMaxPitch = parseFloat(pitchSlider.value);
    let safePitch = userMaxPitch;

    // View perpendicular to the slope rather than skimming parallel to rock
    if (slopeAngleDeg > 8.0) {
      const perpPitch = Math.max(34, 76 - slopeAngleDeg * 1.15);
      safePitch = Math.min(safePitch, perpPitch);
    }

    // Forward slope gradient anticipation along trail
    const aheadPt = getPointAtDistance(dCurr + 0.200);
    if (aheadPt) {
      const dDistM = (aheadPt.dist_km - currPt.dist_km) * 1000;
      if (dDistM > 20) {
        const dEleM = aheadPt.ele - currPt.ele;
        const trailSlopeGrade = dEleM / dDistM;
        if (trailSlopeGrade > 0.08) {
          const trailSlopeDeg = Math.atan(trailSlopeGrade) * 180 / Math.PI;
          safePitch = Math.min(safePitch, Math.max(34, 76 - trailSlopeDeg * 1.3));
        }
      }
    }

    // Line of sight terrain clearance from the valley-standoff camera eye
    if (map && typeof map.queryTerrainElevation === "function") {
      const radEffective = effectiveBearing * Math.PI / 180;
      const eyeDistM = 650;
      const radPitch = (currentPitch * Math.PI) / 180;
      const groundBehindM = eyeDistM * Math.sin(radPitch);
      const eyeHeightM = eyeDistM * Math.cos(radPitch);

      const dLatEye = (-groundBehindM * Math.cos(radEffective)) / 111320;
      const dLonEye = (-groundBehindM * Math.sin(radEffective)) / (111320 * Math.cos(currPt.lat * Math.PI / 180));
      const eyeLon = currPt.lon + dLonEye;
      const eyeLat = currPt.lat + dLatEye;
      const midLon = currPt.lon + dLonEye * 0.5;
      const midLat = currPt.lat + dLatEye * 0.5;

      const elevEyeTerrain = map.queryTerrainElevation([eyeLon, eyeLat]);
      const elevMidTerrain = map.queryTerrainElevation([midLon, midLat]);

      const expectedEyeAlt = currPt.ele + eyeHeightM;
      const expectedMidAlt = currPt.ele + eyeHeightM * 0.5;

      if (elevEyeTerrain !== null && elevEyeTerrain !== undefined) {
        const eyeClearance = expectedEyeAlt - elevEyeTerrain;
        if (eyeClearance < 50) {
          const deficit = 50 - eyeClearance;
          safePitch = Math.min(safePitch, Math.max(30, safePitch - Math.min(25, deficit * 0.2)));
        }
      }

      if (elevMidTerrain !== null && elevMidTerrain !== undefined) {
        const midClearance = expectedMidAlt - elevMidTerrain;
        if (midClearance < 30) {
          const deficit = 30 - midClearance;
          safePitch = Math.min(safePitch, Math.max(32, safePitch - Math.min(20, deficit * 0.15)));
        }
      }
    }

    targetPitch = safePitch;
    currentPitch += (targetPitch - currentPitch) * 0.08;

    return { bearing: effectiveBearing, pitch: currentPitch };
  }

  function moveCameraToIndex(idxFloat) {
    const pt = getPointAtIdx(idxFloat);
    if (!pt) return;

    const { bearing, pitch } = computeCorridorFlight(pt);

    if (markerCursor) markerCursor.setLngLat([pt.lon, pt.lat]);
    if (map) {
      map.jumpTo({
        center: [pt.lon, pt.lat],
        bearing: bearing,
        pitch: pitch,
        zoom: currentZoom
      });
    } else if (cesiumViewer) {
      const cesHeight = 550 * Math.pow(2, 14.0 - currentZoom);
      cesiumViewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, pt.ele + cesHeight),
        orientation: {
          heading: Cesium.Math.toRadians(bearing),
          pitch: Cesium.Math.toRadians(-90 + pitch),
          roll: 0
        }
      });
    }
    scrubber.value = Math.round(idxFloat);
    updateHUD(idxFloat);
    drawElevationProfile(idxFloat);
  }

  function stepFlythrough() {
    if (!isPlaying) return;
    const speed = parseFloat(speedSelect.value) * 1.3;
    playProgress += speed;
    if (playProgress >= track.length - 1) {
      playProgress = track.length - 1;
      stopFlythrough();
      return;
    }
    moveCameraToIndex(playProgress);
    animFrame = requestAnimationFrame(stepFlythrough);
  }

  function startFlythrough() {
    if (playProgress >= track.length - 2) playProgress = 0;
    isPlaying = true;
    playBtn.innerHTML = "&#10074;&#10074; Pause";
    animFrame = requestAnimationFrame(stepFlythrough);
  }

  function stopFlythrough() {
    isPlaying = false;
    playBtn.innerHTML = "&#9654; Fly Route";
    if (animFrame) cancelAnimationFrame(animFrame);
  }

  playBtn.addEventListener("click", () => {
    if (isPlaying) stopFlythrough();
    else startFlythrough();
  });

  document.getElementById("btn-reset").addEventListener("click", () => {
    stopFlythrough();
    playProgress = 0;
    isInitialFrame = true;
    lockedBearing = null;
    isBearingLocked = false;
    currentValleyBias = 0;
    targetValleyBias = 0;
    currentPitch = parseFloat(pitchSlider.value);
    if (map && track.length) {
      const lons = track.map(p => p.lon);
      const lats = track.map(p => p.lat);
      map.fitBounds(
        [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        { padding: 60, pitch: 55, duration: 1200 }
      );
    }
    updateHUD(0);
    drawElevationProfile(0);
  });

  scrubber.addEventListener("input", e => {
    stopFlythrough();
    playProgress = parseFloat(e.target.value);
    isInitialFrame = true;
    lockedBearing = null;
    isBearingLocked = false;
    currentValleyBias = 0;
    targetValleyBias = 0;
    moveCameraToIndex(playProgress);
  });

  exagSlider.addEventListener("input", () => {
    if (map && map.getTerrain()) {
      const src = engineSelect.value === "mapbox3d" ? "mapbox-dem" : "terrainDem";
      map.setTerrain({ source: src, exaggeration: parseFloat(exagSlider.value) });
    }
    updateHUD(playProgress);
  });

  pitchSlider.addEventListener("input", () => {
    currentPitch = parseFloat(pitchSlider.value);
    if (map) map.setPitch(currentPitch);
    updateHUD(playProgress);
  });

  zoomSlider.addEventListener("input", () => {
    currentZoom = parseFloat(zoomSlider.value);
    if (map) map.setZoom(currentZoom);
    updateHUD(playProgress);
  });

  engineSelect.addEventListener("change", e => initMapEngine(e.target.value));

  document.getElementById("btn-keys").addEventListener("click", () => {
    document.getElementById("input-mapbox-token").value = mapboxToken;
    document.getElementById("input-google-key").value = googleKey;
    document.getElementById("key-modal").classList.remove("hidden");
  });
  document.getElementById("btn-close-keys").addEventListener("click", () => {
    document.getElementById("key-modal").classList.add("hidden");
  });
  document.getElementById("btn-save-keys").addEventListener("click", () => {
    mapboxToken = document.getElementById("input-mapbox-token").value.trim();
    googleKey = document.getElementById("input-google-key").value.trim();
    localStorage.setItem("AGY_MAPBOX_TOKEN", mapboxToken);
    localStorage.setItem("AGY_GOOGLE_3D_KEY", googleKey);
    document.getElementById("key-modal").classList.add("hidden");
    if (googleKey) {
      engineSelect.value = "google3d";
      initMapEngine("google3d");
    } else if (mapboxToken) {
      engineSelect.value = "mapbox3d";
      initMapEngine("mapbox3d");
    }
  });

  // Client-side file upload parser (KML, CSV, GPX, Raw Text)
  document.getElementById("file-upload").addEventListener("change", ev => {
    const file = ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result;
      const numRe = /[-+]?\d+(?:\.\d+)?/g;
      let newPts = [];
      if (file.name.endsWith(".gpx") || text.includes("<trkpt")) {
        const doc = new DOMParser().parseFromString(text, "text/xml");
        doc.querySelectorAll("trkpt, rtept").forEach(pt => {
          const lat = parseFloat(pt.getAttribute("lat"));
          const lon = parseFloat(pt.getAttribute("lon"));
          const eleEl = pt.querySelector("ele");
          const ele = eleEl ? parseFloat(eleEl.textContent) : 2200;
          newPts.push({ lat, lon, ele });
        });
      } else if (file.name.endsWith(".kml") || text.includes("<kml")) {
        const doc = new DOMParser().parseFromString(text, "text/xml");
        doc.querySelectorAll("coordinates").forEach(node => {
          node.textContent.trim().split(/\s+/).forEach(tok => {
            const p = tok.split(",");
            if (p.length >= 2) {
              newPts.push({ lon: parseFloat(p[0]), lat: parseFloat(p[1]), ele: p[2] ? parseFloat(p[2]) : 2200 });
            }
          });
        });
      } else {
        text.split(/\r?\n/).forEach(line => {
          const m = line.match(numRe);
          if (m && m.length >= 2) {
            const a = parseFloat(m[0]), b = parseFloat(m[1]);
            if (!isNaN(a) && !isNaN(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180) {
              newPts.push({ lat: a, lon: b, ele: m[2] ? parseFloat(m[2]) : 2200 });
            }
          }
        });
      }
      if (newPts.length > 1) {
        let d = 0;
        track = newPts.map((p, idx) => {
          if (idx > 0) {
            const dy = (p.lat - newPts[idx - 1].lat) * 111.32;
            const dx = (p.lon - newPts[idx - 1].lon) * 111.32 * Math.cos(p.lat * Math.PI / 180);
            d += Math.hypot(dx, dy);
          }
          return { lat: p.lat, lon: p.lon, ele: p.ele, dist_km: d };
        });
        data.title = file.name;
        data.stats.total_distance_km = d.toFixed(2);
        updateHeader();
        initMapEngine(engineSelect.value);
      }
    };
    reader.readAsText(file);
  });

  updateHeader();
  initMapEngine("terrain3d");
})();
