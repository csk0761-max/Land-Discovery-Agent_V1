import React, { useState, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    MapContainer, TileLayer, Circle, Marker, Polyline,
    Popup, Polygon, useMap, FeatureGroup
} from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
    Search, Zap, Wind, Sun, MapPin, AlertCircle,
    FileText, Download, Loader, ChevronRight, BrainCircuit,
    SlidersHorizontal, Layers, FileDown, FileCode,
    Maximize2, Minimize2
} from 'lucide-react';
import html2pdf from 'html2pdf.js';
import './AutoSearchAgent.css';

// Fix Leaflet default icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Numbered candidate marker
function createRankedIcon(rank, score) {
    const color = score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#94a3b8';
    return L.divIcon({
        className: '',
        html: `<div style="
            background:${color};color:white;border:2px solid white;
            border-radius:50%;width:28px;height:28px;
            display:flex;align-items:center;justify-content:center;
            font-weight:700;font-size:12px;
            box-shadow:0 2px 6px rgba(0,0,0,0.35);">
            ${rank}
        </div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
    });
}

// Substation marker
const substationIcon = L.divIcon({
    className: '',
    html: `<div style="
        background:#f59e0b;color:white;border:2px solid white;
        border-radius:4px;width:24px;height:24px;
        display:flex;align-items:center;justify-content:center;
        font-size:13px;box-shadow:0 2px 6px rgba(0,0,0,0.35);">
        ⚡
    </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
});

function MapFitter({ candidates, searchCenter }) {
    const map = useMap();
    React.useEffect(() => {
        if (candidates && candidates.length > 0) {
            const bounds = candidates.map(c => [c.lat, c.lon]);
            if (searchCenter?.lat) bounds.push([searchCenter.lat, searchCenter.lon]);
            map.fitBounds(bounds, { padding: [30, 30] });
        } else if (searchCenter?.lat && searchCenter?.lon) {
            map.setView([searchCenter.lat, searchCenter.lon], Math.max(6, 14 - Math.floor((searchCenter.radius_km || 50) / 20)));
        } else {
            // Default view of India
            map.setView([20.5937, 78.9629], 5);
        }
    }, [candidates, searchCenter]);
    return null;
}

const STEPS = [
    'Initialising GEE search grid…',
    'Scoring candidate sites (slope, land cover, solar/wind resource)…',
    'Checking environmental protection zones…',
    'Finding nearest substations via OSM…',
    'Estimating transmission routes…',
    'Generating AI-ranked report with Gemini…',
];

export default function AutoSearchAgent() {
    const [stateName, setStateName] = useState('Rajasthan');
    const [districtName, setDistrictName] = useState('');
    const [projectType, setProjectType] = useState('solar');
    const [capacityMw, setCapacityMw] = useState('100');
    const [areaAcres, setAreaAcres] = useState('500');
    const [substationQuery, setSubstationQuery] = useState('');

    const [searchCenter, setSearchCenter] = useState(null);
    const [customPolygon, setCustomPolygon] = useState([]);
    
    // Weighting State
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [weights, setWeights] = useState({ slope: 30, land: 25, resource: 25, environment: 20 });
    
    // Layer Overlay State
    const [activeLayers, setActiveLayers] = useState({ slope: false, land_cover: false, solar_ghi: false });
    const [layerUrls, setLayerUrls] = useState({});

    const [loading, setLoading] = useState(false);
    const [loadingStep, setLoadingStep] = useState(0);
    const [error, setError] = useState('');
    const [report, setReport] = useState('');
    const [candidates, setCandidates] = useState([]);
    const [selectedCandidate, setSelectedCandidate] = useState(null);
    const [isExpanded, setIsExpanded] = useState(false);
    const reportRef = useRef(null);

    // HITL State
    const [feedbackText, setFeedbackText] = useState("");
    const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
    const [feedbackSuccess, setFeedbackSuccess] = useState(false);

    const submitFeedback = async () => {
        if (!feedbackText.trim()) return;
        setIsSubmittingFeedback(true);
        setFeedbackSuccess(false);
        try {
            const resp = await fetch('http://localhost:8000/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    context: `Auto Search for ${projectType} in ${districtName || ''} ${stateName}. Capacity: ${capacityMw}MW.`,
                    correction: feedbackText
                })
            });
            if (resp.ok) {
                setFeedbackText("");
                setFeedbackSuccess(true);
                setTimeout(() => setFeedbackSuccess(false), 3000);
            } else {
                alert("Failed to save feedback.");
            }
        } catch(e) {
            alert("Error reaching API.");
        } finally {
            setIsSubmittingFeedback(false);
        }
    };

    // Simulate step progress during the long backend call
    const simulateSteps = useCallback(() => {
        let step = 0;
        const interval = setInterval(() => {
            step++;
            setLoadingStep(prev => Math.min(prev + 1, STEPS.length - 1));
            if (step >= STEPS.length - 1) clearInterval(interval);
        }, 12000); // Each step ~12s
        return () => clearInterval(interval);
    }, []);

    const toggleLayer = async (layerId) => {
        const isActive = !activeLayers[layerId];
        setActiveLayers(prev => ({...prev, [layerId]: isActive}));
        
        if(isActive && !layerUrls[layerId]) {
            try {
                // Use a default center if we haven't searched yet, or the current center
                const targetLat = searchCenter?.lat || 20.5;
                const targetLon = searchCenter?.lon || 78.9;
                const res = await fetch(`http://localhost:8000/layers/${layerId}/tile-url?lat=${targetLat}&lon=${targetLon}&area_acres=100`);
                if(res.ok) {
                    const data = await res.json();
                    setLayerUrls(prev => ({...prev, [layerId]: data.tileUrl}));
                }
            } catch(e) {
                console.error("Failed to load map layer", layerId, e);
            }
        }
    };

    const handleCreatePolygon = (e) => {
        const { layerType, layer } = e;
        if (layerType === 'polygon') {
            const latlngs = layer.getLatLngs()[0].map(latlng => [latlng.lat, latlng.lng]);
            setCustomPolygon(latlngs);
        }
    };
    
    const handleDeletePolygon = () => setCustomPolygon([]);

    const handleSearch = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setReport('');
        setCandidates([]);
        setSelectedCandidate(null);
        setLoadingStep(0);

        const cleanup = simulateSteps();

        try {
            const payload = {
                state: stateName.trim() || null,
                district: districtName.trim() || null,
                project_type: projectType,
                capacity_mw: parseFloat(capacityMw),
                area_acres: parseFloat(areaAcres),
                substation_query: substationQuery.trim() || null,
                search_polygon: customPolygon.length > 2 ? customPolygon : null,
                weights: weights
            };

            const res = await fetch('http://localhost:8000/auto-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Search failed');
            }

            const data = await res.json();
            console.log('[AutoSearch] Raw API data:', data);
            console.log('[AutoSearch] candidates sample:', data.candidates?.[0]);
            setReport(data.report);
            setCandidates(data.candidates || []);
            setSearchCenter(data.search_center || null);
        } catch (err) {
            setError(err.message || 'An error occurred during auto-search.');
        } finally {
            cleanup();
            setLoading(false);
        }
    };

    const handleDownloadPDF = () => {
        if (!reportRef.current) return;
        html2pdf().set({
            margin: [10, 10],
            filename: `auto_search_report_${Date.now()}.pdf`,
            html2canvas: { scale: 2, useCORS: true },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        }).from(reportRef.current).save();
    };

    const exportToCSV = () => {
        if(!candidates || candidates.length === 0) return;
        const headers = ['Rank', 'Lat', 'Lon', 'Score', 'Slope', 'Land_Type', 'GHI', 'Wind', 'Substation', 'Sub_Dist_km', 'Tx_Length_km'];
        const rows = candidates.map(c => [
            c.rank, c.lat, c.lon, c.score, c.slope, 
            c.land_type, c.ghi, c.wind, 
            c.substation?.name || 'N/A', 
            c.substation?.distance_km || '', 
            c.transmission?.distance_km || ''
        ]);
        const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.map(e => e.join(",")).join("\n");
        const link = document.createElement("a");
        link.href = encodeURI(csvContent);
        link.download = `auto_search_candidates_${Date.now()}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const exportToKML = () => {
        if(!candidates || candidates.length === 0) return;
        let kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Candidate Sites</name>`;
        candidates.forEach(c => {
            kml += `
    <Placemark>
      <name>Site #${c.rank}</name>
      <description>Score: ${c.score}/100, Slope: ${c.slope}, Land: ${c.land_type}</description>
      <Point>
        <coordinates>${c.lon},${c.lat},0</coordinates>
      </Point>
    </Placemark>`;
            if(c.polygon) {
                const coords = c.polygon.map(p => `${p[1]},${p[0]},0`).join(' ') + ` ${c.polygon[0][1]},${c.polygon[0][0]},0`;
                kml += `
    <Placemark>
      <name>Site #${c.rank} Boundary</name>
      <Polygon>
        <outerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>`;
            }
        });
        kml += `
  </Document>
</kml>`;
        const blob = new Blob([kml], {type: 'application/vnd.google-earth.kml+xml'});
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `auto_search_candidates_${Date.now()}.kml`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const mapCenter = searchCenter ? [searchCenter.lat, searchCenter.lon] : [20.5937, 78.9629];
    const radiusMeters = searchCenter?.radius_km ? searchCenter.radius_km * 1000 : 0;

    return (
        <div className="auto-search-container">
            {/* Left: Form */}
            <div className="auto-search-left">
                <div className="glass-card auto-search-form-card">
                    <div className="as-section-header">
                        <Search size={18} color="var(--primary)" />
                        <span>Search Parameters</span>
                    </div>

                    <form onSubmit={handleSearch} className="as-form">
                        <div className="as-field-group">
                            <label className="as-label">
                                <MapPin size={13} /> Search Region
                            </label>
                            <div className="as-row">
                                <input
                                    className="input-field"
                                    placeholder={customPolygon.length > 0 ? "Polygon mode active" : "State (e.g. Rajasthan)"}
                                    value={stateName}
                                    onChange={e => setStateName(e.target.value)}
                                    required={customPolygon.length === 0}
                                    disabled={customPolygon.length > 0}
                                    style={customPolygon.length > 0 ? { opacity: 0.5 } : {}}
                                />
                                <input
                                    className="input-field"
                                    placeholder={customPolygon.length > 0 ? "Polygon mode active" : "District (Optional)"}
                                    value={districtName}
                                    onChange={e => setDistrictName(e.target.value)}
                                    disabled={customPolygon.length > 0}
                                    style={customPolygon.length > 0 ? { opacity: 0.5 } : {}}
                                />
                            </div>
                        </div>

                        <div className="as-field-group">
                            <label className="as-label">Project Type</label>
                            <div className="as-type-toggle">
                                {[['solar', '☀️ Solar'], ['wind', '💨 Wind'], ['both', '⚡ Both']].map(([val, label]) => (
                                    <button
                                        key={val}
                                        type="button"
                                        className={`as-type-btn ${projectType === val ? 'active' : ''}`}
                                        onClick={() => setProjectType(val)}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="as-row">
                            <div className="as-field-group">
                                <label className="as-label">
                                    <Zap size={13} /> Capacity (MW)
                                </label>
                                <input
                                    className="input-field"
                                    type="number" min="1"
                                    placeholder="e.g. 100"
                                    value={capacityMw}
                                    onChange={e => setCapacityMw(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="as-field-group">
                                <label className="as-label">
                                    <MapPin size={13} /> Area (acres)
                                </label>
                                <input
                                    className="input-field"
                                    type="number" min="1"
                                    placeholder="e.g. 500"
                                    value={areaAcres}
                                    onChange={e => setAreaAcres(e.target.value)}
                                    required
                                />
                            </div>
                        </div>

                        <div className="as-field-group">
                            <label className="as-label">
                                <Zap size={13} /> Preferred Substation (optional)
                            </label>
                            <input
                                className="input-field"
                                placeholder="e.g. Ramgarh 220kV"
                                value={substationQuery}
                                onChange={e => setSubstationQuery(e.target.value)}
                            />
                        </div>

                        <div className="as-advanced-toggle" onClick={() => setShowAdvanced(!showAdvanced)}>
                            <SlidersHorizontal size={14} /> 
                            <span>{showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings'}</span>
                        </div>
                        
                        {showAdvanced && (
                            <div className="as-advanced-panel">
                                <div className="weight-slider-row">
                                    <label>Topography <span>{weights.slope}%</span></label>
                                    <input type="range" min="0" max="100" value={weights.slope} onChange={(e) => setWeights({...weights, slope: parseInt(e.target.value)})} />
                                </div>
                                <div className="weight-slider-row">
                                    <label>Land Use Profile <span>{weights.land}%</span></label>
                                    <input type="range" min="0" max="100" value={weights.land} onChange={(e) => setWeights({...weights, land: parseInt(e.target.value)})} />
                                </div>
                                <div className="weight-slider-row">
                                    <label>Resource <span>{weights.resource}%</span></label>
                                    <input type="range" min="0" max="100" value={weights.resource} onChange={(e) => setWeights({...weights, resource: parseInt(e.target.value)})} />
                                </div>
                                <div className="weight-slider-row">
                                    <label>Restrictions <span>{weights.environment}%</span></label>
                                    <input type="range" min="0" max="100" value={weights.environment} onChange={(e) => setWeights({...weights, environment: parseInt(e.target.value)})} />
                                </div>
                            </div>
                        )}

                        <button className="btn-primary as-submit" type="submit" disabled={loading}>
                            {loading ? (
                                <><Loader size={16} className="spin-inline" /> Searching…</>
                            ) : (
                                <><Search size={16} /> Run Auto Search</>
                            )}
                        </button>
                    </form>
                </div>

                {/* Candidate List */}
                {candidates.length > 0 && (
                    <div className="glass-card candidate-list-card">
                        <div className="as-section-header">
                            <FileText size={16} color="var(--primary)" />
                            <span>Top {candidates.length} Sites Found</span>
                        </div>
                        <div className="candidate-list">
                            {candidates.map(c => {
                                const score = c.score;
                                const color = score >= 70 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#94a3b8';
                                return (
                                    <div
                                        key={c.rank}
                                        className={`candidate-row ${selectedCandidate?.rank === c.rank ? 'selected' : ''}`}
                                        onClick={() => setSelectedCandidate(c)}
                                    >
                                        <div className="candidate-rank-badge" style={{ background: color }}>
                                            #{c.rank}
                                        </div>
                                        <div className="candidate-info">
                                            <span className="candidate-coords">
                                                {Number(c.lat).toFixed(4)}, {Number(c.lon).toFixed(4)}
                                            </span>
                                            <span className="candidate-meta">
                                                {c.land_type} · Slope {c.slope}°
                                                {c.substation?.name && ` · ${c.substation.name}`}
                                            </span>
                                        </div>
                                        <div className="candidate-score" style={{ color }}>
                                            {score}<span>/100</span>
                                        </div>
                                        <ChevronRight size={14} color="#94a3b8" />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>

            {/* Center: Map */}
            <div className="auto-search-center glass-card as-map-card">
                <div className="as-map-header">
                    <span className="as-map-title">
                        <MapPin size={15} color="var(--primary)" /> Site Map
                    </span>
                    <div className="as-map-legend">
                        <span><span className="legend-dot green" />Top site</span>
                        <span><span className="legend-dot amber" />Good site</span>
                        <span><span className="legend-dot gray" />Fair site</span>
                        <span>⚡ Substation</span>
                    </div>
                </div>
                
                {/* Custom Layer Control */}
                <div className="custom-layer-control">
                    <div className="layer-title"><Layers size={14}/> Live API Overlays</div>
                    <label className="layer-label"><input type="checkbox" checked={activeLayers.slope} onChange={() => toggleLayer('slope')} /> Terrain Slope</label>
                    <label className="layer-label"><input type="checkbox" checked={activeLayers.land_cover} onChange={() => toggleLayer('land_cover')} /> Land Cover</label>
                    <label className="layer-label"><input type="checkbox" checked={activeLayers.solar_ghi} onChange={() => toggleLayer('solar_ghi')} /> Solar GHI</label>
                </div>

                <div className="as-map-container">
                    <MapContainer
                        center={mapCenter}
                        zoom={8}
                        style={{ height: '100%', width: '100%' }}
                    >
                        {activeLayers.slope && layerUrls.slope && <TileLayer url={layerUrls.slope} opacity={0.5} zIndex={400} attribution="Copernicus DEM 30m" />}
                        {activeLayers.land_cover && layerUrls.land_cover && <TileLayer url={layerUrls.land_cover} opacity={0.6} zIndex={401} attribution="Google Dynamic World" />}
                        {activeLayers.solar_ghi && layerUrls.solar_ghi && <TileLayer url={layerUrls.solar_ghi} opacity={0.5} zIndex={402} attribution="MODIS MCD18A1" />}

                        <TileLayer
                            attribution='&copy; <a href="https://maps.google.com">Google Maps Satellite</a>'
                            url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                            maxZoom={20}
                        />
                        <MapFitter
                            candidates={candidates}
                            searchCenter={searchCenter}
                        />
                        
                        <FeatureGroup>
                            <EditControl
                                position="topright"
                                onCreated={handleCreatePolygon}
                                onDeleted={handleDeletePolygon}
                                draw={{
                                    rectangle: false, circle: false, circlemarker: false, marker: false, polyline: false,
                                    polygon: { allowIntersection: false, drawError: { color: '#e1e100', message: "Intersection" }, shapeOptions: { color: '#f59e0b', weight: 3, fillOpacity: 0.2 } }
                                }}
                            />
                        </FeatureGroup>

                        {/* Search radius circle */}
                        {searchCenter && radiusMeters > 0 && (
                            <Circle
                                center={mapCenter}
                                radius={radiusMeters}
                                pathOptions={{ color: '#006cb5', fillColor: '#006cb5', fillOpacity: 0.06, dashArray: '6,4' }}
                            />
                        )}

                        {/* Candidate markers + transmission lines + substation markers */}
                        {candidates.map(c => (
                            <React.Fragment key={c.rank}>
                                {/* Transmission line */}
                                {c.transmission?.waypoints?.length > 1 && (
                                    <Polyline
                                        positions={c.transmission.waypoints}
                                        pathOptions={{
                                            color: selectedCandidate?.rank === c.rank ? '#006cb5' : '#94a3b8',
                                            weight: selectedCandidate?.rank === c.rank ? 2.5 : 1.5,
                                            dashArray: '5,5',
                                            opacity: selectedCandidate?.rank === c.rank ? 0.9 : 0.5,
                                        }}
                                    />
                                )}

                                {/* Substation marker */}
                                {c.substation?.lat && (
                                    <Marker
                                        position={[c.substation.lat, c.substation.lon]}
                                        icon={substationIcon}
                                    >
                                        <Popup>
                                            <strong>⚡ {c.substation.name}</strong><br />
                                            {c.substation.distance_km} km from Site #{c.rank}
                                        </Popup>
                                    </Marker>
                                )}

                                {/* Site Polygon (Requested Acreage Boundary) */}
                                {c.polygon && (
                                    <Polygon
                                        positions={c.polygon}
                                        pathOptions={{
                                            color: selectedCandidate?.rank === c.rank ? '#006cb5' : (c.score >= 70 ? '#22c55e' : c.score >= 50 ? '#f59e0b' : '#94a3b8'),
                                            fillColor: selectedCandidate?.rank === c.rank ? '#006cb5' : (c.score >= 70 ? '#22c55e' : c.score >= 50 ? '#f59e0b' : '#94a3b8'),
                                            fillOpacity: selectedCandidate?.rank === c.rank ? 0.4 : 0.2,
                                            weight: selectedCandidate?.rank === c.rank ? 3 : 2
                                        }}
                                        eventHandlers={{ click: () => setSelectedCandidate(c) }}
                                    >
                                        <Popup>
                                            <strong>Site #{c.rank} — Score: {c.score}/100</strong><br />
                                            📍 {Number(c.lat).toFixed(5)}, {Number(c.lon).toFixed(5)}<br />
                                            🏔️ Slope: {c.slope}°<br />
                                            🌿 Land: {c.land_type}<br />
                                            ☀️ GHI: {c.ghi} kWh/m²/day<br />
                                            💨 Wind: {c.wind} m/s<br />
                                            ⚡ Substation: {c.substation?.name || 'N/A'} ({c.substation?.distance_km ?? '?'} km)<br />
                                            🛣️ Tx Route: {c.transmission?.distance_km ?? '?'} km ({c.transmission?.difficulty})<br />
                                            📐 Area: {areaAcres} acres
                                        </Popup>
                                    </Polygon>
                                )}

                                {/* Numbered Center Marker */}
                                <Marker
                                    position={[c.lat, c.lon]}
                                    icon={createRankedIcon(c.rank, c.score)}
                                    eventHandlers={{ click: () => setSelectedCandidate(c) }}
                                    interactive={false} // Let the polygon under it handle the click/popup
                                />
                            </React.Fragment>
                        ))}
                    </MapContainer>
                </div>
            </div>

            {/* Right: Report Panel */}
            <div className={`auto-search-right glass-card as-report-card ${isExpanded ? 'as-report-expanded' : ''}`}>
                {error && (
                    <div className="error-message">
                        <AlertCircle size={18} /> {error}
                    </div>
                )}

                {!report && !loading && !error && (
                    <div className="as-placeholder">
                        <Search size={56} color="#94a3b8" strokeWidth={1} />
                        <h3>Awaiting Auto Search</h3>
                        <p>Set your parameters and click <strong>Run Auto Search</strong> to identify the best renewable energy sites in the area.</p>
                    </div>
                )}

                {loading && (
                    <div className="as-loading">
                        <div className="loader dark" style={{ width: 40, height: 40, borderWidth: 4 }} />
                        <h3>Scanning Search Area…</h3>
                        <div className="as-steps">
                            {STEPS.map((step, i) => (
                                <div key={i} className={`as-step ${i < loadingStep ? 'done' : i === loadingStep ? 'active' : 'pending'}`}>
                                    <span className="as-step-dot" />
                                    <span>{step}</span>
                                </div>
                            ))}
                        </div>
                        <p className="as-loading-note">This may take 3–5 minutes while GEE processes the search grid.</p>
                    </div>
                )}

                {report && !loading && (
                    <div className="as-report-body" style={{ animation: 'fadeIn 0.5s ease-out' }}>
                        <div className="as-report-header">
                            <h2>Auto Search Report</h2>
                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: 0 }}>
                                <button onClick={() => setIsExpanded(!isExpanded)} className="btn-secondary" style={{ width: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                                    {isExpanded ? <><Minimize2 size={14} /> Collapse</> : <><Maximize2 size={14} /> Expand</>}
                                </button>
                                <button onClick={exportToCSV} className="btn-secondary" style={{ width: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                                    <FileDown size={14} /> CSV
                                </button>
                                <button onClick={exportToKML} className="btn-secondary" style={{ width: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                                    <FileCode size={14} /> KML
                                </button>
                                <button onClick={handleDownloadPDF} className="btn-primary" style={{ width: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                                    <Download size={14} /> PDF
                                </button>
                            </div>
                        </div>
                        <div className="markdown-body" ref={reportRef} style={{ background: '#fff', padding: '1.5rem', borderRadius: 10, border: '1px solid #e2e8f0' }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                        </div>
                        
                        {/* RAG / Human-In-The-Loop Feedback Panel */}
                        <div className="hitl-feedback-panel glass-card" style={{ marginTop: '2rem', padding: '1rem', border: '1px solid rgba(59, 130, 246, 0.4)', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.7)' }}>
                            <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, marginBottom: '0.5rem', color: 'var(--primary-hover)', fontSize: '0.95rem' }}>
                            <BrainCircuit size={16} /> Human-In-The-Loop AI Memory
                            </h4>
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', lineHeight: 1.4 }}>
                            Provide expert feedback below to teach the AI what to look for when evaluating similar future regions. This insight will be permanently stored and retrieved via RAG.
                            </p>
                            <textarea 
                                className="form-input" 
                                rows={3} 
                                value={feedbackText} 
                                onChange={(e) => setFeedbackText(e.target.value)} 
                                placeholder="E.g. In this specific region, a slope up to 12 degrees is perfectly acceptable..." 
                                style={{ resize: 'vertical', minHeight: '60px' }}
                            />
                            <div style={{ display: 'flex', alignItems: 'center', marginTop: '0.75rem', gap: '1rem' }}>
                            <button 
                                className="btn-primary" 
                                onClick={submitFeedback}
                                disabled={!feedbackText.trim() || isSubmittingFeedback}
                                style={{ width: 'auto', padding: '0.5rem 1.25rem', marginTop: 0 }}
                            >
                                {isSubmittingFeedback ? 'Memorizing...' : 'Teach AI'}
                            </button>
                            {feedbackSuccess && <span style={{ color: '#22c55e', fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>✓ Rule Memorized & Distributed</span>}
                            </div>
                        </div>

                    </div>
                )}
            </div>
        </div>
    );
}
