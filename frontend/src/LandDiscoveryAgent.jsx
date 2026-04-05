import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  MapContainer, TileLayer, Circle, useMap, Marker, FeatureGroup, Polyline, Popup, Polygon, WMSTileLayer, useMapEvents 
} from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import { kml } from '@tmcw/togeojson';
import { DOMParser } from '@xmldom/xmldom';
import JSZip from 'jszip';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import L from 'leaflet';
import { MapPin, Maximize, Compass, Search, AlertCircle, FileText, Minimize2, Maximize2, Download, BrainCircuit, Zap, Loader, Shield, Database } from 'lucide-react';
import html2pdf from 'html2pdf.js';
import Logo from './Logo';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import LayerControlPanel from './LayerControlPanel';
import AutoSearchAgent from './AutoSearchAgent';
import './LandDiscoveryAgent.css';

// Component to dynamically update map center when coordinates change
function MapUpdater({ center }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, map.getZoom(), { animate: true, duration: 1.5 });
  }, [center, map]);
  return null;
}

// Component to handle map clicks for Revenue Map Identification
function MapClickHandler({ active, onMapClick }) {
  useMapEvents({
    click: (e) => {
      if (active) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

function LandDiscoveryAgent() {
  const navigate = useNavigate();
  const [lat, setLat] = useState('27.0238');
  const [lon, setLon] = useState('71.9213');
  const [coordInput, setCoordInput] = useState('27.0238, 71.9213');
  const [inputType, setInputType] = useState('manual'); // 'manual' or 'kml'
  const [substationMode, setSubstationMode] = useState('auto'); // 'auto' | 'manual'
  const [manualGss, setManualGss] = useState('');
  const [manualGssDistance, setManualGssDistance] = useState(null);
  const [nearbyGss, setNearbyGss] = useState([]);
  const [selectedGss, setSelectedGss] = useState('');
  const [isFetchingGss, setIsFetchingGss] = useState(false);
  const [propertyInfo, setPropertyInfo] = useState(null);
  const [isFetchingLoc, setIsFetchingLoc] = useState(false);
  const [revenueMapActive, setRevenueMapActive] = useState(false);
  const [wmsConfig, setWmsConfig] = useState(null);
  const [plotInfo, setPlotInfo] = useState(null);
  const [area, setArea] = useState('600.0');
  const [polygonCoords, setPolygonCoords] = useState(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [activeTab, setActiveTab] = useState('parcel');
  
  // Data Moat State
  const [intelTargetGss, setIntelTargetGss] = useState('');
  const [intelText, setIntelText] = useState('');
  const [intelStatus, setIntelStatus] = useState(null);
  const [isSubmittingIntel, setIsSubmittingIntel] = useState(false);


  const processKmlText = (text) => {
    try {
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(text, "text/xml");
      const converted = kml(xmlDoc);

      if (converted.features && converted.features.length > 0) {
        // Extract the first polygon feature from the KML GeoJSON
        const firstFeature = converted.features[0];
        if (firstFeature.geometry.type === 'Polygon') {
          const rawCoords = firstFeature.geometry.coordinates[0];
          // togeojson returns [lng, lat], we need [lat, lng] for Leaflet
          const formattedCoords = rawCoords.map(c => [c[1], c[0]]);
          setPolygonCoords(formattedCoords);
        } else {
          alert("Uploaded file does not contain a standard valid Polygon shape.");
        }
      } else {
        alert("No features found in the uploaded file.");
      }
    } catch (err) {
      alert("Failed to parse file.");
      console.error(err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const fileName = file.name.toLowerCase();

    if (fileName.endsWith('.kmz')) {
      try {
        const jszip = new JSZip();
        const zip = await jszip.loadAsync(file);

        // Find the main .kml file inside the .kmz archive (usually doc.kml)
        const kmlFile = Object.values(zip.files).find(f => f.name.toLowerCase().endsWith('.kml'));

        if (kmlFile) {
          const kmlText = await kmlFile.async('text');
          processKmlText(kmlText);
        } else {
          alert("No .kml file found inside the .kmz archive.");
        }
      } catch (err) {
        alert("Failed to extract KMZ archive.");
        console.error(err);
      }
    } else {
      // Handle standard .kml
      const reader = new FileReader();
      reader.onload = (event) => {
        processKmlText(event.target.result);
      };
      reader.readAsText(file);
    }
  };

  const _onEdited = e => {
    e.layers.eachLayer(layer => {
      const latlngs = layer.getLatLngs()[0];
      setPolygonCoords(latlngs.map(ll => [ll.lat, ll.lng]));
    });
  };

  const _onCreated = e => {
    const layer = e.layer;
    const latlngs = layer.getLatLngs()[0];
    setPolygonCoords(latlngs.map(ll => [ll.lat, ll.lng]));
  };

  const _onDeleted = e => {
    setPolygonCoords(null);
  };

  const reportRef = useRef(null);

  const handleDownloadPDF = () => {
    if (!reportRef.current) return;
    const opt = {
      margin: [0.5, 0.5, 0.5, 0.5],
      filename: `Land_Discovery_Report_${lat}_${lon}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(reportRef.current).save();
  };

  const [mapExpanded, setMapExpanded] = useState(true);
  const [reportExpanded, setReportExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState('');
  const [error, setError] = useState('');

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
          context: `Coordinates: ${lat}, ${lon}. Area: ${area} acres. Custom Prompt: ${customPrompt}`,
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

  const submitIntelligence = async () => {
    if (!intelTargetGss.trim() || !intelText.trim()) return;
    setIsSubmittingIntel(true);
    setIntelStatus(null);
    try {
      const resp = await fetch('http://localhost:8000/upload-intelligence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          substation_name: intelTargetGss,
          intelligence_text: intelText
        })
      });
      if (resp.ok) {
        setIntelText("");
        setIntelTargetGss("");
        setIntelStatus("success");
        setTimeout(() => setIntelStatus(null), 3500);
      } else {
        setIntelStatus("error");
      }
    } catch(e) {
      setIntelStatus("error");
    } finally {
      setIsSubmittingIntel(false);
    }
  };


  // Layer control state
  const [activeTileLayers, setActiveTileLayers] = useState([]);
  const [reportLayers, setReportLayers] = useState([]);
  const [layerThumbnails, setLayerThumbnails] = useState({});

  const handleLayersChange = useCallback((activeLayers, selectedReportLayers, thumbnails) => {
    setActiveTileLayers(activeLayers);
    setReportLayers(selectedReportLayers);
    setLayerThumbnails(thumbnails || {});
  }, []);

  // Calculate radius from acres (1 acre = 4046.86 sq meters)
  // Area = pi * r^2  => r = sqrt(Area / pi)
  const calcRadius = (acres) => {
    const sqMeters = parseFloat(acres || 0) * 4046.86;
    return Math.sqrt(sqMeters / Math.PI);
  };

  const handleCoordChange = (e) => {
    const val = e.target.value;
    setCoordInput(val);
    if(val.includes(',')) {
      const parts = val.split(',');
      if(parts.length === 2 && !isNaN(parseFloat(parts[0])) && !isNaN(parseFloat(parts[1]))) {
        const newLat = parts[0].trim();
        const newLon = parts[1].trim();
        setLat(newLat);
        setLon(newLon);
        setNearbyGss([]);
        setSelectedGss('');
        setManualGss('');
        setManualGssDistance(null);
        setPropertyInfo(null);
        updateLocationCard(newLat, newLon);
      }
    }
  };

  const haversineDist = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  };

  const handleManualGssChange = (e) => {
    const val = e.target.value;
    setManualGss(val);
    if(val.includes(',')) {
      const parts = val.split(',');
      if(parts.length === 2 && !isNaN(parseFloat(parts[0])) && !isNaN(parseFloat(parts[1]))) {
        const d = haversineDist(parseFloat(lat), parseFloat(lon), parseFloat(parts[0]), parseFloat(parts[1]));
        setManualGssDistance(d.toFixed(2));
      } else {
        setManualGssDistance(null);
      }
    } else {
      setManualGssDistance(null);
    }
  };

  const fetchNearbyGss = async () => {
    if(!lat || !lon) return;
    setIsFetchingGss(true);
    try {
      const res = await fetch(`http://localhost:8000/find-substations?lat=${lat}&lon=${lon}&radius_m=20000`);
      if(res.ok) {
        const data = await res.json();
        setNearbyGss(data);
        if(data.length > 0) setSelectedGss(data[0].name);
      } else {
        alert("Failed to fetch substations.");
      }
    } catch(err) {
      console.error(err);
    } finally {
      setIsFetchingGss(false);
    }
  };

  const fetchWmsConfig = async (stateName) => {
    try {
      const res = await fetch(`http://localhost:8000/revenue/wms-config?state=${stateName}`);
      if (res.ok) {
        const data = await res.json();
        setWmsConfig(data);
      }
    } catch (e) {
      console.error("WMS config fetch error:", e);
    }
  };

  const handleMapClick = async (clickedLat, clickedLon) => {
    if (!revenueMapActive) return;
    setPlotInfo({ loading: true });
    try {
      const stateName = propertyInfo?.state || 'Rajasthan';
      const res = await fetch(`http://localhost:8000/revenue/plot-info?lat=${clickedLat}&lon=${clickedLon}&state=${stateName}`);
      if (res.ok) {
        const data = await res.json();
        setPlotInfo(data);
      }
    } catch (e) {
      console.error("Plot info fetch error:", e);
      setPlotInfo({ error: "System Busy" });
    }
  };

  // Helper to fetch just location details for the sidebar card
  const updateLocationCard = async (l, lo) => {
    try {
        const res = await fetch(`http://localhost:8000/location-details?lat=${l}&lon=${lo}`);
        if(res.ok) {
            const data = await res.json();
            setPropertyInfo(data);
        }
    } catch(e) {}
  };

  const fetchPropertyInfo = async () => {
    if(!lat || !lon) return;
    setIsFetchingLoc(true);
    try {
      const res = await fetch(`http://localhost:8000/find-substations?lat=${lat}&lon=${lon}&radius_m=1`); // Quick hack to get location? No, let's use a dedicated endpoint or wait.
      // Actually, let's just use the existing GSS fetch to trigger location inside its logic or add a small one.
      // Best: Just trigger whenever lat/lon stops changing.
      const resLoc = await fetch(`http://localhost:1234/NOT_REAL`); // We'll just update logic below.
    } catch(e) {} finally { setIsFetchingLoc(false); }
  };

  const getPortalInfo = (stateName) => {
    const portals = {
        'Rajasthan': { name: 'E-Dharti / Apna Khata', url: 'https://apnakhata.rajasthan.gov.in/' },
        'Gujarat': { name: 'AnyROR Gujarat', url: 'https://anyror.gujarat.gov.in/' },
        'Maharashtra': { name: 'Mahabhulekh', url: 'https://bhulekh.mahabhulekh.maharashtra.gov.in/' },
        'Madhya Pradesh': { name: 'Bhulekh MP', url: 'https://mpbhulekh.gov.in/' },
        'Andhra Pradesh': { name: 'Meebhoomi', url: 'http://meebhoomi.ap.gov.in/' },
        'Karnataka': { name: 'Bhoomi RTC', url: 'https://landrecords.karnataka.gov.in/' }
    };
    return portals[stateName] || { name: 'Bhu-Naksha (All India)', url: 'https://bhunaksha.gov.in/' };
  };

  const getSelectedGssPos = () => {
    if (substationMode === 'auto' && selectedGss) {
      const gss = nearbyGss.find(g => g.name === selectedGss);
      if (gss) return [gss.lat, gss.lon];
    } else if (substationMode === 'manual' && manualGss.includes(',')) {
      const parts = manualGss.split(',');
      if (parts.length === 2 && !isNaN(parseFloat(parts[0])) && !isNaN(parseFloat(parts[1]))) {
        return [parseFloat(parts[0].trim()), parseFloat(parts[1].trim())];
      }
    }
    return null;
  };
  const selectedGssPos = getSelectedGssPos();

  // Auto-fetch GSS when coordinates change in auto mode
  useEffect(() => {
    if (substationMode === 'auto' && lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon))) {
      const timeoutId = setTimeout(() => {
        fetchNearbyGss();
      }, 500); 
      return () => clearTimeout(timeoutId);
    }
  }, [lat, lon, substationMode]);

  // Handle case where Analyze is clicked before auto-fetch completes
  const ensureGssFetched = async () => {
    if (substationMode === 'auto' && nearbyGss.length === 0 && !isFetchingGss) {
      console.log("Analyze clicked but no GSS info - forcing fetch...");
      await fetchNearbyGss();
    }
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await ensureGssFetched();
      const payload = {
        area_acres: parseFloat(area),
      };

      if (inputType === 'manual') {
        payload.lat = parseFloat(lat);
        payload.lon = parseFloat(lon);
      } else {
        // for KML, use the first coordinate of the polygon as the center approximation for Geocoding tools
        if (polygonCoords && polygonCoords.length > 0) {
          payload.lat = polygonCoords[0][0];
          payload.lon = polygonCoords[0][1];
        } else {
          throw new Error("Please upload a valid KML file with a polygon before analyzing.");
        }
      }

      if (customPrompt.trim().length > 0) {
        payload.custom_prompt = customPrompt.trim();
      }

      if (polygonCoords && polygonCoords.length > 2) {
        payload.polygon = polygonCoords;
      }

      if (substationMode === 'auto' && selectedGss) {
        const gssObj = nearbyGss.find(g => g.name === selectedGss);
        if(gssObj) payload.gss_info = `${gssObj.name} (Distance: ${gssObj.distance_km} km)`;
      } else if (substationMode === 'manual' && manualGssDistance) {
        payload.gss_info = `Manual Coordinate [${manualGss}] (Distance: ${manualGssDistance} km)`;
      }

      // Pass selected report layers and their thumbnail URLs to the agent
      if (reportLayers.length > 0) {
        payload.selected_layers = reportLayers;
      }
      if (Object.keys(layerThumbnails).length > 0) {
        payload.layer_thumbnails = layerThumbnails;
      }

      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Analysis failed. Please check your API connection.');
      }

      const data = await response.json();
      setReport(data.report);
      setMapExpanded(false);
    } catch (err) {
      setError(err.message || 'An error occurred during analysis.');
    } finally {
      setLoading(false);
    }
  };


  const position = [parseFloat(lat) || 0, parseFloat(lon) || 0];
  const radiusMeters = calcRadius(area);

  return (
    <div className="app-container">
      <header className="header">
        <button
          onClick={() => navigate('/')}
          className="back-button"
        >
          <ArrowLeft size={16} /> Back to Hub
        </button>
        <div className="header-brand">
          <Logo width="180px" />
          <div className="header-titles">
            <h2>Land Discovery Platform</h2>
            <p>Real-time GIS intelligence and AI feasibility assessment for renewable energy.</p>
          </div>
        </div>
      </header>

      <div className="agent-tabs" style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.25rem', justifyContent: 'center' }}>
        <button
          className={`agent-tab-btn ${activeTab === 'parcel' ? 'active' : ''}`}
          onClick={() => setActiveTab('parcel')}
        >
          <MapPin size={16} /> Parcel Analysis
        </button>
        <button
          className={`agent-tab-btn ${activeTab === 'auto_search' ? 'active' : ''}`}
          onClick={() => setActiveTab('auto_search')}
        >
          <Search size={16} /> Auto Search Land with AI
        </button>
      </div>

      {activeTab === 'parcel' ? (
        <div className="main-content">
          {/* Left Input & Map Panel */}
          <div className="left-panel">
            <div className="glass-card">
              <h3 style={{ color: 'var(--primary-hover)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Compass size={20} color="var(--primary)" /> Parcel Details
              </h3>

              <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                <div className="input-toggle-container" style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="inputType"
                      value="manual"
                      checked={inputType === 'manual'}
                      onChange={(e) => setInputType(e.target.value)}
                    />
                    Manual Coordinates
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="inputType"
                      value="kml"
                      checked={inputType === 'kml'}
                      onChange={(e) => setInputType(e.target.value)}
                    />
                    Upload KML/KMZ
                  </label>
                </div>

                {inputType === 'manual' ? (
                  <div className="input-group">
                    <label className="label-wrap">
                      <MapPin size={16} /> Coordinates (Lat, Lon)
                    </label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="e.g. 27.0238, 71.9213"
                      value={coordInput}
                      onChange={handleCoordChange}
                      required
                    />
                  </div>
                ) : (
                  <div className="input-group" style={{
                    border: '1px dashed #cbd5e1',
                    padding: '1rem',
                    borderRadius: '8px',
                    background: '#f8fafc',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                    alignItems: 'center'
                  }}>
                    <label style={{ fontSize: '0.9rem', color: '#475569', fontWeight: 500 }}>
                      Upload Boundary (.KML / .KMZ)
                    </label>
                    <input
                      type="file"
                      accept=".kml,.kmz"
                      onChange={handleFileUpload}
                      style={{ fontSize: '0.8rem' }}
                    />
                  </div>
                )}

                {/* Land Identification & State Records Card */}
                <div style={{ 
                    background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
                    padding: '1rem',
                    borderRadius: '12px',
                    border: '1px solid #bae6fd',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.75rem',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#0369a1', fontWeight: 600, fontSize: '0.9rem' }}>
                        <BrainCircuit size={18} /> Land Identification (Conceptual)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                        <div style={{ fontSize: '0.8rem' }}>
                            <div style={{ color: '#64748b', fontWeight: 500 }}>Village/Area</div>
                            <div style={{ color: '#1e293b' }}>{propertyInfo ? propertyInfo.village : (isFetchingLoc ? "..." : "Pending")}</div>
                        </div>
                        <div style={{ fontSize: '0.8rem' }}>
                            <div style={{ color: '#64748b', fontWeight: 500 }}>Tehsil/Taluka</div>
                            <div style={{ color: '#1e293b' }}>{propertyInfo ? propertyInfo.tehsil : (isFetchingLoc ? "..." : "Pending")}</div>
                        </div>
                    </div>
                    <button 
                        type="button"
                        className="btn-primary" 
                        style={{ 
                            background: '#0ea5e9', 
                            fontSize: '0.8rem', 
                            padding: '0.5rem',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            gap: '0.5rem'
                        }}
                        onClick={() => window.open(getPortalInfo(propertyInfo?.state).url, '_blank')}
                    >
                        <FileText size={14} /> Search {getPortalInfo(propertyInfo?.state).name}
                    </button>
                </div>

                <div className="input-group" style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <label className="label-wrap" style={{ marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Zap size={15} /> Grid Substation (GSS)</span>
                    <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.8rem', fontWeight: 400 }}>
                      <label style={{ cursor:'pointer' }}><input type="radio" value="auto" checked={substationMode==='auto'} onChange={()=>setSubstationMode('auto')} /> Auto</label>
                      <label style={{ cursor:'pointer' }}><input type="radio" value="manual" checked={substationMode==='manual'} onChange={()=>setSubstationMode('manual')} /> Manual</label>
                    </div>
                  </label>
                  
                  {substationMode === 'auto' ? (
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <select 
                        className="input-field" 
                        value={selectedGss} 
                        onChange={(e) => setSelectedGss(e.target.value)}
                        style={{ flex: 1, padding: '0.4rem', fontSize: '0.85rem' }}
                        disabled={nearbyGss.length === 0}
                      >
                        {nearbyGss.length === 0 ? <option value="">No GSS fetched yet</option> : nearbyGss.map((g, i) => (
                          <option key={i} value={g.name}>
                            {g.name} [{g.voltage||'??'}kV] — {g.distance_km}km (Est: {g.capacity_mw}MW)
                          </option>
                        ))}
                      </select>
                      <button type="button" onClick={fetchNearbyGss} className="btn-secondary" style={{ width: 'auto', padding: '0 0.75rem', whiteSpace: 'nowrap', fontSize: '0.8rem' }} disabled={isFetchingGss}>
                        {isFetchingGss ? <Loader size={12} className="spin-inline" /> : <Search size={12} />} Re-Scan
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <input 
                        type="text" 
                        className="input-field" 
                        placeholder="Paste GSS Lat, Lon..." 
                        value={manualGss} 
                        onChange={handleManualGssChange}
                        style={{ flex: 1, padding: '0.4rem', fontSize: '0.85rem' }}
                      />
                      {manualGssDistance && <span style={{ fontSize: '0.8rem', color: '#006cb5', fontWeight: 600, whiteSpace: 'nowrap' }}>{manualGssDistance} km</span>}
                    </div>
                  )}
                </div>

                <div className="input-group">
                  <label className="label-wrap">
                    <Maximize size={16} /> Area (Acres)
                  </label>
                  <input
                    type="number"
                    step="any"
                    required
                    className="input-field"
                    value={area}
                    onChange={(e) => setArea(e.target.value)}
                  />
                </div>

                <div className="input-group">
                  <label className="label-wrap">
                    <FileText size={16} /> Optional: Advanced AI Directives
                  </label>
                  <textarea
                    className="input-field"
                    placeholder="e.g. Focus specifically on geotechnical risks, or ignore minor water bodies..."
                    rows="2"
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    style={{ resize: 'vertical' }}
                  />
                </div>



                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? (
                    <>
                      <div className="loader"></div> Processing GIS Data...
                    </>
                  ) : (
                    <>
                      <Search size={20} /> Run AI Analysis
                    </>
                  )}
                </button>
              </form>
            </div>
            
            {/* PROPRIETARY DATA MOAT VAULT */}
            <div className="glass-card" style={{ padding: '1rem', borderTop: '4px solid #ef4444' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontWeight: 600, color: '#ef4444' }}>
                <Shield size={18} /> Proprietary Intelligence Vault
              </div>
              <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '1rem', lineHeight: 1.4 }}>
                Upload confidential grid feasibility data (e.g. Substation capacity constraints). The AI Memory will retrieve it whenever scanning near this GSS.
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="Target GSS Name (e.g. Bhadla GSS)" 
                  value={intelTargetGss}
                  onChange={(e) => setIntelTargetGss(e.target.value)}
                  style={{ padding: '0.5rem', fontSize: '0.85rem' }}
                />
                <textarea 
                  className="input-field"
                  placeholder="Enter specific capacity congestion or interconnection rules here..."
                  rows="3"
                  value={intelText}
                  onChange={(e) => setIntelText(e.target.value)}
                  style={{ padding: '0.5rem', fontSize: '0.85rem', resize: 'vertical' }}
                />
                <button 
                  onClick={submitIntelligence}
                  disabled={isSubmittingIntel || !intelTargetGss || !intelText}
                  className="btn-primary"
                  style={{ padding: '0.6rem', background: '#ef4444', fontSize: '0.85rem', marginTop: 0 }}
                >
                  {isSubmittingIntel ? <Loader size={14} className="spin-inline"/> : <Database size={14} />} Embed into Data Moat
                </button>
                {intelStatus === 'success' && <div style={{ color: '#10b981', fontSize: '0.8rem', textAlign: 'center' }}>Securely Embedded ✓</div>}
                {intelStatus === 'error' && <div style={{ color: '#ef4444', fontSize: '0.8rem', textAlign: 'center' }}>Failed to Embed</div>}
              </div>
            </div>

            {/* GEE Layer Control Panel */}
            <LayerControlPanel
              lat={lat || '27.0238'}
              lon={lon || '71.9213'}
              area={area || '100'}
              onLayersChange={handleLayersChange}
            />
          </div>

          {/* Center Map Panel */}
          <div className="center-panel glass-card">
            <div className="map-header">
              <h4 style={{ color: 'var(--primary-hover)', margin: 0 }}>Location Preview</h4>
              <button
                type="button"
                className="map-toggle-btn"
                onClick={() => setMapExpanded(!mapExpanded)}
              >
                {mapExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                {mapExpanded ? 'Minimize' : 'Expand'}
              </button>
            </div>

            <div className={`map-container ${mapExpanded ? 'expanded' : 'minimised'}`} style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column' }}>
              {!isNaN(position[0]) && !isNaN(position[1]) && (
                <MapContainer center={position} zoom={13} style={{ height: '100%', width: '100%', zIndex: 1, minHeight: '300px' }}>
                  <TileLayer
                    attribution='&copy; <a href="https://maps.google.com">Google Maps Satellite</a>'
                    url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                    maxZoom={20}
                  />

                  {revenueMapActive && wmsConfig && (
                    <WMSTileLayer
                      url={wmsConfig.wms_url}
                      layers={wmsConfig.layer}
                      format="image/png"
                      transparent={true}
                      version="1.1.1"
                      opacity={0.8}
                    />
                  )}

                  {/* Active GEE overlay layers */}
                  {activeTileLayers.map(layer => (
                    <TileLayer
                      key={layer.id}
                      url={layer.tileUrl}
                      attribution={layer.attribution}
                      opacity={0.75}
                    />
                  ))}
                  
                  {/* Grid Substation Markers */}
                  {nearbyGss.map((g, i) => (
                    <Marker 
                      key={`gss-${i}`} 
                      position={[g.lat, g.lon]}
                      icon={L.divIcon({
                        className: 'gss-marker',
                        html: `<div style="background: rgba(239, 68, 68, 0.4); width: 10px; height: 10px; border-radius: 50%; border: 1px solid white;"></div>`,
                        iconSize: [10, 10]
                      })}
                    >
                      <Popup>
                        <strong>GSS: {g.name}</strong><br/>
                        Distance: {g.distance_km} km
                      </Popup>
                    </Marker>
                  ))}

                  {/* Selected GSS Pin & Aerial Line */}
                  {selectedGssPos && (
                    <>
                      <Marker 
                        position={selectedGssPos}
                        zIndexOffset={1000}
                        icon={L.divIcon({
                          className: 'selected-gss-marker',
                          html: `<div style="background: #2563eb; width: 18px; height: 18px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 15px rgba(37, 99, 235, 0.6); display: flex; align-items: center; justify-content: center;"><div style="color: white; font-size: 10px;">⚡</div></div>`,
                          iconSize: [18, 18]
                        })}
                      >
                        <Popup>
                          <strong>Target Grid Interconnection</strong><br/>
                          {substationMode === 'auto' ? selectedGss : 'Manual Node'}
                        </Popup>
                      </Marker>
                      <Polyline 
                        positions={[position, selectedGssPos]} 
                        pathOptions={{ 
                          color: '#2563eb', 
                          weight: 3, 
                          dashArray: '8, 12', 
                          opacity: 0.7,
                          lineCap: 'round'
                        }} 
                      />
                    </>
                  )}

                  <MapUpdater center={position} />
                  <MapClickHandler active={revenueMapActive} onMapClick={handleMapClick} />
                  
                  <FeatureGroup>
                    <EditControl
                      position="topright"
                      onEdited={_onEdited}
                      onCreated={_onCreated}
                      onDeleted={_onDeleted}
                      draw={{
                        rectangle: false,
                        circle: false,
                        circlemarker: false,
                        marker: false,
                        polyline: false,
                      }}
                    />
                    {!polygonCoords && (
                      <Circle
                        center={position}
                        radius={radiusMeters}
                        pathOptions={{ color: '#006cb5', fillColor: '#006cb5', fillOpacity: 0.2 }}
                      />
                    )}
                  </FeatureGroup>
                </MapContainer>
              )}
            </div>
            <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.75rem', textAlign: 'center' }}>
              {polygonCoords ? 'Using custom drawn polygon boundaries for analysis' : `Blue circle represents the approximate ${area} acre boundary`}
            </p>
          </div>

          {/* Right Results Panel */}
          <div className={`results-panel glass-card ${reportExpanded ? 'ld-report-expanded' : ''}`}>
            {error && (
              <div className="error-message">
                <AlertCircle size={20} /> {error}
              </div>
            )}

            {!report && !loading && !error && (
              <div className="results-placeholder">
                <FileText size={64} color="#94a3b8" strokeWidth={1} />
                <h2 style={{ color: 'var(--primary-hover)' }}>Awaiting Analysis</h2>
                <p>Input coordinates and area to generate an expert Land Feasibility Report using Google Earth Engine and Gemini AI.</p>
              </div>
            )}

            {loading && !report && (
              <div className="results-placeholder">
                <div className="loader dark" style={{ width: 40, height: 40, borderWidth: 4 }}></div>
                <h3 style={{ color: 'var(--primary-hover)' }}>Extracting Live Earth Engine Data...</h3>
                <p>Measuring Topology, Climate metrics, and environment risk.</p>
              </div>
            )}

            {report && (
              <div style={{ animation: 'fadeIn 0.5s ease-out', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h2 style={{ color: 'var(--primary-hover)', margin: 0 }}>Analysis Report</h2>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: 0 }}>
                    <button onClick={() => setReportExpanded(!reportExpanded)} className="btn-secondary" style={{ width: 'auto', padding: '0.5rem 1rem' }}>
                      {reportExpanded ? <><Minimize2 size={16} /> Collapse</> : <><Maximize2 size={16} /> Expand</>}
                    </button>
                    <button onClick={handleDownloadPDF} className="btn-primary" style={{ width: 'auto', padding: '0.5rem 1rem' }}>
                      <Download size={16} /> Download PDF
                    </button>
                  </div>
                </div>
                <div className="markdown-body" ref={reportRef} style={{ background: '#ffffff', padding: '2rem', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                </div>

                {/* RAG / Human-In-The-Loop Feedback Panel */}
                <div className="hitl-feedback-panel glass-card" style={{ marginTop: '2rem', padding: '1rem', border: '1px solid rgba(59, 130, 246, 0.4)', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.7)' }}>
                  <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, marginBottom: '0.5rem', color: 'var(--primary-hover)', fontSize: '0.95rem' }}>
                    <BrainCircuit size={16} /> Human-In-The-Loop AI Memory
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem', lineHeight: 1.4 }}>
                    Did the AI miss a nuanced rule? Provide expert feedback below to teach the AI what to look for when evaluating similar future domains. This insight will be permanently stored and retrieved via RAG.
                  </p>
                  <textarea 
                    className="form-input" 
                    rows={3} 
                    value={feedbackText} 
                    onChange={(e) => setFeedbackText(e.target.value)} 
                    placeholder="E.g. In this specific district, a slope up to 12 degrees is perfectly acceptable for racking systems..." 
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
      ) : (
        <AutoSearchAgent />
      )}
    </div>
  );
}

export default LandDiscoveryAgent;
