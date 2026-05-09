import React, { useState, useEffect, useRef, useCallback } from 'react';
import { kml } from '@tmcw/togeojson';
import { DOMParser } from '@xmldom/xmldom';
import JSZip from 'jszip';
import { MapContainer, TileLayer, FeatureGroup, Polyline, CircleMarker, Marker, Popup, Tooltip, useMap, useMapEvents, Polygon, Circle } from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import { MapPin, Maximize, Compass, Search, AlertCircle, FileText, Minimize2, Maximize2, Download, Zap, Loader, Shield, Layers, Map as MapIcon, FileWarning, MessageSquarePlus, Radar, LogOut } from 'lucide-react';
import html2pdf from 'html2pdf.js';
import { useNavigate } from 'react-router-dom';
import { supabase } from './supabaseClient';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import LayerControlPanel from './LayerControlPanel';
import LandDiscoveryReportPanel from './land-discovery/LandDiscoveryReportPanel';
import { adminHeaders, apiUrl, authHeaders } from './api';
import './LandDiscoveryAgent.css';

// Fix for Leaflet default marker icons in Vite/React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Map Controller for auto-zoom and bounds management
const MapController = ({ lat, lon, area, polygonCoords }) => {
  const map = useMap();

  useEffect(() => {
    if (!map) return undefined;

    let cancelled = false;
    const runViewportUpdate = () => {
      if (cancelled) return;

      try {
        map.invalidateSize({ pan: false });
      } catch (err) {
        console.warn('Leaflet invalidateSize failed:', err);
      }

      const size = typeof map.getSize === 'function' ? map.getSize() : null;
      if (!size || !size.x || !size.y) return;

      if (polygonCoords && polygonCoords.length > 2) {
        const bounds = L.latLngBounds(polygonCoords.map((c) => [c[0], c[1]]));
        map.fitBounds(bounds, { padding: [50, 50], animate: true });
        return;
      }

      if (lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon))) {
        const center = [parseFloat(lat), parseFloat(lon)];
        if (area && !isNaN(parseFloat(area)) && parseFloat(area) > 0) {
          const areaSqM = parseFloat(area) * 4046.86;
          const radiusM = Math.sqrt(areaSqM / Math.PI);
          const circle = L.circle(center, { radius: radiusM });
          map.fitBounds(circle.getBounds(), { padding: [100, 100], animate: true });
        } else {
          map.flyTo(center, 15, { animate: true });
        }
      }
    };

    if (typeof map.whenReady === 'function') {
      map.whenReady(() => {
        requestAnimationFrame(runViewportUpdate);
      });
    } else {
      requestAnimationFrame(runViewportUpdate);
    }

    return () => {
      cancelled = true;
    };
  }, [lat, lon, area, polygonCoords, map]);

  return null;
};

const chhattisgarhDistrictAliases = {
  balod: '62',
  'baloda bazar': '50',
  'baloda bazar bhatapara': '50',
  balodabazar: '50',
  'balodabazar bhatapara': '50',
  balrampur: '65',
  'balrampur ramanujganj': '65',
  bastar: '45',
  bemetara: '52',
  bijapur: '47',
  bilaspur: '40',
  dantewada: '61',
  dhamtari: '59',
  durg: '43',
  'gaurela pendra marwahi': '66',
  gariaband: '51',
  'janjgir champa': '54',
  jashpur: '56',
  kabirdham: '57',
  kanker: '60',
  'khairagarh chhuikhadan gandai': '67',
  kondagaon: '49',
  korba: '55',
  korea: '53',
  mahasamund: '58',
  'manendragarh chirmiri bharatpur': '71',
  'mohla manpur ambagarh chowki': '68',
  mungeli: '63',
  narayanpur: '46',
  raigarh: '41',
  raipur: '44',
  rajnandgaon: '42',
  sakti: '69',
  'sarangarh bilaigarh': '70',
  sukma: '48',
  surajpur: '64',
  surguja: '39',
};

const normalizeLookupName = (value) =>
  String(value || '')
    .toLowerCase()
    .replace(/district/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

function LandDiscoveryAgent() {
  const navigate = useNavigate();
  const [lat, setLat] = useState('27.0238');
  const [lon, setLon] = useState('71.9213');
  const [coordInput, setCoordInput] = useState('27.0238, 71.9213');
  const [inputType, setInputType] = useState('manual'); // 'manual' or 'kml'
  const [substationMode, setSubstationMode] = useState('auto'); // 'auto' | 'manual'
  const [gssRadiusKm, setGssRadiusKm] = useState('50');
  const [manualGss, setManualGss] = useState('');
  const [manualGssDistance, setManualGssDistance] = useState(null);
  const [nearbyGss, setNearbyGss] = useState([]);
  const [transmissionLines, setTransmissionLines] = useState([]);
  const [transmissionLineSource, setTransmissionLineSource] = useState('');
  const [isFetchingLines, setIsFetchingLines] = useState(false);
  const [selectedGss, setSelectedGss] = useState('');

  // Define core fetching logic early so handlers can use them
  const fetchTransmissionLines = useCallback(async (l, lo) => {
    const plat = parseFloat(l);
    const plon = parseFloat(lo);
    if (isNaN(plat) || isNaN(plon)) return;
    setIsFetchingLines(true);
    try {
      const res = await fetch(apiUrl(`/api/transmission-lines?lat=${plat}&lon=${plon}&radius_m=25000`));
      if (res.ok) {
        const data = await res.json();
        const lines = Array.isArray(data) ? data : (data?.lines || []);
        setTransmissionLines(lines);
        setTransmissionLineSource(Array.isArray(data) ? '' : (data?.source_mode || ''));
      }
    } catch (err) {
      console.error("Failed to fetch transmission lines:", err);
    } finally {
      setIsFetchingLines(false);
    }
  }, []);

  const updateLocationCard = useCallback(async (l, lo) => {
    if (!l || !lo) return;
    try {
        setIsFetchingLoc(true);
        const res = await fetch(apiUrl(`/location-details?lat=${l}&lon=${lo}`));
        if (res.ok) {
            const data = await res.json();
            setPropertyInfo(data);
        }
        fetchNearbyPlaces(l, lo);
        fetchTransmissionLines(l, lo);
    } catch (err) {
        console.error("Location lookup failed:", err);
    } finally {
        setIsFetchingLoc(false);
    }
  }, [fetchTransmissionLines]);
  const [isFetchingGss, setIsFetchingGss] = useState(false);
  const [gssScanStatus, setGssScanStatus] = useState('');
  const [autoGssResults, setAutoGssResults] = useState([]);
  const [autoGssLoading, setAutoGssLoading] = useState(false);
  const [autoGssError, setAutoGssError] = useState('');
  const [autoGssDistanceFilter, setAutoGssDistanceFilter] = useState('25');
  const [autoGssVoltageFilter, setAutoGssVoltageFilter] = useState('all');
  const [autoGssSummary, setAutoGssSummary] = useState(null);
  const [propertyInfo, setPropertyInfo] = useState(null);
  const [isFetchingLoc, setIsFetchingLoc] = useState(false);
  const [nearbyPlaces, setNearbyPlaces] = useState([]);
  const [, setIsFetchingPlaces] = useState(false);
  const [revenueMapActive] = useState(false);
  const [plotInfo, setPlotInfo] = useState(null);
  const [area, setArea] = useState('600.0');
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [polygonCoords, setPolygonCoords] = useState(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [activeTab] = useState('parcel');
  
  // Data Moat State
  const [intelTargetGss, setIntelTargetGss] = useState('');
  const [intelText, setIntelText] = useState('');
  const [intelStatus, setIntelStatus] = useState(null);
  const [isSubmittingIntel, setIsSubmittingIntel] = useState(false);
  
  // Layout Management State
  const [leftWidth, setLeftWidth] = useState(360);
  const [rightWidth, setRightWidth] = useState(420);
  const [isLeftMinimized, setIsLeftMinimized] = useState(true);
  const [isRightMinimized, setIsRightMinimized] = useState(true);
  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);
  
  const gssFetchSeqRef = useRef(0);
  const autoGssSeqRef = useRef(0);

  // Mapbox Refs - Removed for Leaflet

  const handleMouseMove = useCallback((e) => {
    if (isResizingLeft) {
      const newWidth = e.clientX;
      if (newWidth > 100 && newWidth < 700) {
        setLeftWidth(newWidth);
        if (newWidth < 120 && !isLeftMinimized) setIsLeftMinimized(true);
        if (newWidth >= 120 && isLeftMinimized) setIsLeftMinimized(false);
      }
    } else if (isResizingRight) {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth > 100 && newWidth < 800) {
        setRightWidth(newWidth);
        if (newWidth < 120 && !isRightMinimized) setIsRightMinimized(true);
        if (newWidth >= 120 && isRightMinimized) setIsRightMinimized(false);
      }
    }
  }, [isResizingLeft, isResizingRight, isLeftMinimized, isRightMinimized]);

  const handleMouseUp = useCallback(() => {
    setIsResizingLeft(false);
    setIsResizingRight(false);
    document.body.style.cursor = 'default';
  }, []);

  useEffect(() => {
    if (isResizingLeft || isResizingRight) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingLeft, isResizingRight, handleMouseMove, handleMouseUp]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 820) {
        setIsLeftMinimized(false);
        setIsRightMinimized(false);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getLandAnchor = useCallback(() => {
    if (polygonCoords && polygonCoords.length > 2) {
      const sum = polygonCoords.reduce((acc, point) => {
        acc.lat += Number(point[0]) || 0;
        acc.lon += Number(point[1]) || 0;
        return acc;
      }, { lat: 0, lon: 0 });
      return {
        lat: sum.lat / polygonCoords.length,
        lon: sum.lon / polygonCoords.length,
      };
    }
    const parsedLat = Number(lat);
    const parsedLon = Number(lon);
    if (Number.isFinite(parsedLat) && Number.isFinite(parsedLon)) {
      return { lat: parsedLat, lon: parsedLon };
    }
    return null;
  }, [lat, lon, polygonCoords]);

  const fetchAutoGssFinder = useCallback(async () => {
    const anchor = getLandAnchor();
    if (!anchor) return;
    const requestId = ++autoGssSeqRef.current;
    setAutoGssLoading(true);
    setAutoGssError('');
    try {
      const response = await fetch(apiUrl('/api/gss/auto-finder'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({
          lat: anchor.lat,
          lon: anchor.lon,
          radius_km: 25,
        }),
      });
      if (!response.ok) {
        throw new Error(`Auto GSS Finder failed: ${response.statusText}`);
      }
      const data = await response.json();
      if (requestId !== autoGssSeqRef.current) return;
      setAutoGssResults(data.results || []);
      setAutoGssSummary(data.summary || null);
    } catch (err) {
      if (requestId === autoGssSeqRef.current) {
        setAutoGssError(err.message || 'Auto GSS Finder failed.');
        setAutoGssResults([]);
        setAutoGssSummary(null);
      }
    } finally {
      if (requestId === autoGssSeqRef.current) {
        setAutoGssLoading(false);
      }
    }
  }, [getLandAnchor]);

  useEffect(() => {
    const anchor = getLandAnchor();
    if (!anchor) return undefined;
    const timer = setTimeout(() => {
      fetchAutoGssFinder();
    }, 500);
    return () => clearTimeout(timer);
  }, [fetchAutoGssFinder, getLandAnchor]);

  const processKmlText = (text) => {
    try {
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(text, "text/xml");
      const converted = kml(xmlDoc);

      if (converted.features && converted.features.length > 0) {
        const polygonFeature = converted.features.find((feature) => {
          const geometryType = feature?.geometry?.type;
          return geometryType === 'Polygon' || geometryType === 'MultiPolygon';
        });

        if (polygonFeature) {
          const rawCoords = polygonFeature.geometry.type === 'Polygon'
            ? polygonFeature.geometry.coordinates[0]
            : polygonFeature.geometry.coordinates[0][0];
          const formattedCoords = rawCoords.map(c => [c[1], c[0]]);
          return {
            polygonCoords: formattedCoords,
            fullGeoJSON: converted,
          };
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

    return null;
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const fileName = file.name.toLowerCase();
    setUploadedFileName(file.name);
    setKmlGeoJSON(null);

    if (fileName.endsWith('.kmz')) {
      try {
        const jszip = new JSZip();
        const zip = await jszip.loadAsync(file);

        // Find the main .kml file inside the .kmz archive (usually doc.kml)
        const kmlFile = Object.values(zip.files).find(f => f.name.toLowerCase().endsWith('.kml'));

        if (kmlFile) {
          const kmlText = await kmlFile.async('text');
          const parsed = processKmlText(kmlText);
          if (parsed) {
            setKmlGeoJSON(parsed.fullGeoJSON);
            setPolygonCoords(parsed.polygonCoords);
            const centroid = parsed.polygonCoords.reduce((acc, point) => ({
              lat: acc.lat + point[0],
              lon: acc.lon + point[1],
            }), { lat: 0, lon: 0 });
            const centerLat = centroid.lat / parsed.polygonCoords.length;
            const centerLon = centroid.lon / parsed.polygonCoords.length;
            setLat(String(centerLat));
            setLon(String(centerLon));
            setCoordInput(`${centerLat}, ${centerLon}`);
            setTransmissionLines([]);
            setIsFetchingLines(false);
            updateLocationCard(centerLat, centerLon);

            // Upload to Supabase for cloud backup
            try {
              const formData = new FormData();
              formData.append('file', file);
              await fetch(apiUrl(`/api/storage/upload?bucket=documents&path=surveys/${Date.now()}_${file.name}`), {
                method: 'POST',
                headers: authHeaders(),
                body: formData,
              });
              console.log('KMZ file successfully backed up to Supabase Cloud.');
            } catch (uploadErr) {
              console.error('Failed to backup KMZ file to cloud:', uploadErr);
            }
          }
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
        (async () => {
          const parsed = processKmlText(event.target.result);
          if (parsed) {
            setKmlGeoJSON(parsed.fullGeoJSON);
            setPolygonCoords(parsed.polygonCoords);
            const centroid = parsed.polygonCoords.reduce((acc, point) => ({
              lat: acc.lat + point[0],
              lon: acc.lon + point[1],
            }), { lat: 0, lon: 0 });
            const centerLat = centroid.lat / parsed.polygonCoords.length;
            const centerLon = centroid.lon / parsed.polygonCoords.length;
            setLat(String(centerLat));
            setLon(String(centerLon));
            setCoordInput(`${centerLat}, ${centerLon}`);
            setTransmissionLines([]);
            setIsFetchingLines(false);
            updateLocationCard(centerLat, centerLon);

            // Upload to Supabase for cloud backup
            try {
              const formData = new FormData();
              formData.append('file', file);
              await fetch(apiUrl(`/api/storage/upload?bucket=documents&path=surveys/${Date.now()}_${file.name}`), {
                method: 'POST',
                headers: authHeaders(),
                body: formData,
              });
              console.log('File successfully backed up to Supabase Cloud.');
            } catch (uploadErr) {
              console.error('Failed to backup file to cloud:', uploadErr);
            }
          }
        })();
      };
      reader.readAsText(file);
    }
  };


  const reportRef = useRef(null);

  const handleDownloadPDF = () => {
    const el = reportRef.current;
    if (!el) {
      alert('Report not ready yet. Please wait for the analysis to complete.');
      return;
    }
    
    // Save original styles to restore later
    const originalStyle = {
      position: el.style.position,
      width: el.style.width,
      maxWidth: el.style.maxWidth,
      boxSizing: el.style.boxSizing,
      backgroundColor: el.style.backgroundColor,
      color: el.style.color,
      padding: el.style.padding,
      borderRadius: el.style.borderRadius,
      boxShadow: el.style.boxShadow,
      overflow: el.style.overflow,
      maxHeight: el.style.maxHeight
    };

    // Apply temporary styles for PDF capture (avoiding position: fixed)
    el.style.backgroundColor = '#ffffff';
    el.style.color = '#0f172a';
    el.style.padding = '40px';
    el.style.borderRadius = '0';
    el.style.boxShadow = 'none';
    el.style.width = '794px';
    el.style.maxWidth = '794px';
    el.style.boxSizing = 'border-box';
    el.style.overflow = 'visible';
    el.style.maxHeight = 'none';

    const opt = {
      margin: [0.5, 0.5, 0.5, 0.5],
      filename: `Land_Discovery_Report_${lat || 'site'}_${lon || 'location'}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { 
        scale: 2, 
        useCORS: true, 
        backgroundColor: '#ffffff',
        logging: false,
        windowWidth: 794
      },
      jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    
    html2pdf().set(opt).from(el).save().then(() => {
      // Restore original styles
      Object.keys(originalStyle).forEach(key => {
        el.style[key] = originalStyle[key];
      });
    }).catch(err => {
      console.error('PDF Generation Error:', err);
      // Ensure restoration even on error
      Object.keys(originalStyle).forEach(key => {
        el.style[key] = originalStyle[key];
      });
    });
  };

  const [, setMapExpanded] = useState(true);
  const [reportExpanded, setReportExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Analyzing parcel...");
  const [report, setReport] = useState('');
  const [error, setError] = useState('');

  // HITL State
  const [feedbackText, setFeedbackText] = useState("");
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const abortControllerRef = useRef(null);

  const submitFeedback = async () => {
    if (!feedbackText.trim()) return;
    setIsSubmittingFeedback(true);
    setFeedbackSuccess(false);
    try {
      const resp = await fetch(apiUrl('/feedback'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
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
    } catch {
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
      const resp = await fetch(apiUrl('/upload-intelligence'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
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
    } catch {
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
        setTransmissionLines([]); // Clear old lines
        setIsFetchingLines(false);
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

  const fetchNearbyGss = async (latOverride, lonOverride, radiusKmOverride) => {
    const useLat = latOverride ?? lat;
    const useLon = lonOverride ?? lon;
    const parsedRadiusKm = Number(radiusKmOverride ?? gssRadiusKm);
    const useRadiusKm = Number.isFinite(parsedRadiusKm) && parsedRadiusKm > 0 ? parsedRadiusKm : 50;
    const useRadiusM = Math.round(useRadiusKm * 1000);
    if(!useLat || !useLon) return;
    const requestId = ++gssFetchSeqRef.current;
    setIsFetchingGss(true);
    setGssScanStatus(`Scanning nearby substations within ${useRadiusKm} km...`);
    try {
      const res = await fetch(apiUrl(`/find-substations?lat=${useLat}&lon=${useLon}&radius_m=${useRadiusM}`), {
        headers: authHeaders(),
      });
      if(res.ok) {
        const data = await res.json();
        if (requestId !== gssFetchSeqRef.current) return;
        setNearbyGss(data);
        if(data && data.length > 0) {
          setSelectedGss(data[0].name);
          setGssScanStatus(`Found ${data.length} nearby substations within ${useRadiusKm} km.`);
        } else {
          setSelectedGss('none_found');
          setGssScanStatus(`No substations found within ${useRadiusKm} km.`);
          console.warn(`GSS Scan: No substations found within ${useRadiusKm}km.`);
        }
      } else {
        const errText = await res.text();
        if (requestId === gssFetchSeqRef.current) {
          setGssScanStatus(`Scan failed: ${errText || res.statusText || 'Unknown error'}`);
        }
        console.error('GSS Scan failed:', res.status, errText);
      }
    } catch(err) {
      if (requestId === gssFetchSeqRef.current) {
        setGssScanStatus(`Scan error: ${err.message || 'Network error'}`);
        console.error('GSS Scan network error:', err);
      }
    } finally {
      if (requestId === gssFetchSeqRef.current) {
        setIsFetchingGss(false);
      }
    }
  };

  const handleMapClick = async (clickedLat, clickedLon) => {
    if (!revenueMapActive) return;
    setPlotInfo({ loading: true });
    try {
      const stateName = propertyInfo?.state || 'Rajasthan';
      const res = await fetch(apiUrl(`/revenue/plot-info?lat=${clickedLat}&lon=${clickedLon}&state=${stateName}`));
      if (res.ok) {
        const data = await res.json();
        setPlotInfo(data);
      }
    } catch (err) {
      console.error("Plot info fetch error:", err);
      setPlotInfo({ error: "System Busy" });
    }
  };

  const revenueWarning = plotInfo?.warning || null;

  // Helper to fetch just location details for the sidebar card
  const fetchNearbyPlaces = async (l, lo) => {
    try {
      setIsFetchingPlaces(true);
      const res = await fetch(apiUrl(`/api/nearby-places?lat=${l}&lon=${lo}&radius_m=5000`));
      if (res.ok) {
        const data = await res.json();
        setNearbyPlaces(data || []);
      }
    } catch (err) {
      console.error("Failed to fetch nearby places:", err);
    } finally {
      setIsFetchingPlaces(false);
    }
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

  // Removed Mapbox useEffect hooks. Leaflet uses declarative components.
  
  // Custom component to handle Leaflet map events
  const MapEvents = () => {
    const map = useMap();
    
    useEffect(() => {
      const targetLon = parseFloat(lon);
      const targetLat = parseFloat(lat);
      if (!isNaN(targetLon) && !isNaN(targetLat)) {
        map.flyTo([targetLat, targetLon], map.getZoom() || 13);
      }
    }, [lat, lon, map]);

    useMapEvents({
      click(e) {
        if (revenueMapActive) {
          handleMapClick(e.latlng.lat, e.latlng.lng);
        }
      },
    });
    return null;
  };

  // Handle case where Analyze is clicked before auto-fetch completes
  const ensureGssFetched = async () => {
    if (substationMode === 'auto' && nearbyGss.length === 0 && !isFetchingGss) {
      console.log("Analyze clicked but no GSS info - forcing fetch...");
      await fetchNearbyGss(lat, lon);
    }
  };

  const handleAnalyze = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setLoading(true);
    setError('');

    // Curious Progress Ticker
    const messages = [
      "📡 Scanning satellite imagery for hydrology risk...",
      "⚡ Locating nearest high-voltage transmission lines...",
      "🗳️ Convening the Expert Committee (CrewAI)...",
      "🏗️ Senior Civil Engineer is evaluating terrain slope...",
      "📈 Grid Specialist is reviewing substation capacity...",
      "📊 Investment Lead is finalizing the bankability thesis...",
      "📜 Drafting the Pre-Construction Diligence Report..."
    ];
    let msgIndex = 0;
    const msgInterval = setInterval(() => {
      msgIndex = (msgIndex + 1) % messages.length;
      setLoadingMessage(messages[msgIndex]);
    }, 6000);
    setLoadingMessage(messages[0]);

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

      const controller = new AbortController();
      abortControllerRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 600000); // 10-minute timeout for complex AI reports

      const response = await fetch(apiUrl('/analyze'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        let detail = '';
        try {
          const errorPayload = await response.json();
          detail = errorPayload?.detail || errorPayload?.message || '';
        } catch {
          // Ignore malformed error bodies and fall back to the status text.
        }
        throw new Error(detail ? `Analysis failed: ${detail}` : `Analysis failed (${response.status} ${response.statusText}).`);
      }

      const data = await response.json();
      clearInterval(msgInterval);
      setReport(data.report);
      setMapExpanded(false);
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Analysis took too long or was interrupted. Please check your connection and try again.');
      } else {
        setError(err.message || 'An error occurred during analysis.');
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };
  const handleStopAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut();
      navigate('/login');
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  const selectedGssDistance = (substationMode === 'auto' && selectedGss && selectedGss !== 'none_found') ? nearbyGss.find(g => g.name === selectedGss)?.distance_km : manualGssDistance;
  const formatSummaryNumber = (value) => {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    const parsed = Number(value);
    return Number.isNaN(parsed) ? String(value) : parsed.toFixed(2);
  };
  const filteredAutoGssResults = autoGssResults.filter((item) => {
    const maxDistance = Number(autoGssDistanceFilter);
    const distanceOk = Number.isFinite(maxDistance) ? item.distance_km <= maxDistance : true;
    const voltageOk = autoGssVoltageFilter === 'all'
      ? true
      : String(item.voltage_level || 'unknown').toLowerCase() === autoGssVoltageFilter.toLowerCase();
    return distanceOk && voltageOk;
  });
  const autoGssRemark = autoGssSummary?.risk_remark || (filteredAutoGssResults.length ? 'Review nearest GSS before proceeding.' : 'Low feasibility');
  const transmissionLineVoltageCounts = transmissionLines.reduce((acc, line) => {
    const key = String(line.voltage || 'unknown').toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const transmissionLineVoltageSummary = ['400', '220', '132'].map((voltage) => {
    const count = transmissionLineVoltageCounts[`${voltage}kv`] || transmissionLineVoltageCounts[voltage] || 0;
    return `${voltage}kV ${count}`;
  }).join(' · ');

  return (
    <>
    {activeTab === 'parcel' ? (
      <div className="gss-engine-container">
        {isLeftMinimized && (
          <button type="button" className="floating-reopen-btn" onClick={() => setIsLeftMinimized(false)}>
            <Compass size={16} /> Open workflow
          </button>
        )}
        <div className={`gss-sidebar ${isLeftMinimized ? 'minimized' : ''}`} style={{ width: isLeftMinimized ? '50px' : leftWidth + 'px', minWidth: isLeftMinimized ? '50px' : 'unset' }}>
          <div className="sidebar-inner" style={{ opacity: isLeftMinimized ? 0 : 1, pointerEvents: isLeftMinimized ? 'none' : 'auto', minWidth: isLeftMinimized ? '0' : '340px' }}>
          <div className="gss-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <button onClick={handleLogout} className="back-btn" title="Sign Out"><LogOut size={16} /> Logout</button>
              <button onClick={() => setIsLeftMinimized(!isLeftMinimized)} className="minimize-toggle-btn" title={isLeftMinimized ? "Expand" : "Minimize"}>
                {isLeftMinimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
              </button>
            </div>
            {!isLeftMinimized && (
              <div className="gss-title">
                <h2>Land Discovery</h2>
                <p>GIS Intelligence</p>
              </div>
            )}
          </div>
          
          <div className="agent-tabs" style={{ display: 'none' }}>
          </div>

          <div className="sidebar-scrollable">
            <form onSubmit={handleAnalyze} className="analysis-form">
              <details className="accordion-card" open>
                <summary className="accordion-header">
                  <div style={{display:'flex', alignItems:'center', gap:'0.75rem'}}>
                    <span className="section-step">Step 1</span>
                    <h3 style={{margin:0}}><Compass size={18} /> Define site</h3>
                  </div>
                  <ChevronDown size={18} className="chevron" />
                </summary>
                <div className="accordion-content">




                  <div className="input-toggle-pill">
                    <label className={`toggle-choice ${inputType === 'manual' ? 'active' : ''}`}>
                      <input type="radio" name="inputType" value="manual" checked={inputType === 'manual'} onChange={(e) => setInputType(e.target.value)} />
                      Manual coordinates
                    </label>
                    <label className={`toggle-choice ${inputType === 'kml' ? 'active' : ''}`}>
                      <input type="radio" name="inputType" value="kml" checked={inputType === 'kml'} onChange={(e) => setInputType(e.target.value)} />
                      Upload KML/KMZ
                    </label>
                  </div>

                  {inputType === 'manual' ? (
                    <div className="input-group">
                      <label className="label-wrap"><MapPin size={16} /> Coordinates (Lat, Lon)</label>
                      <input type="text" className="input-field" placeholder="e.g. 27.0238, 71.9213" value={coordInput} onChange={handleCoordChange} required />
                      <span className="field-hint">Use decimal latitude, then longitude. The map and GSS scan update as you type.</span>
                    </div>
                  ) : (
                    <div className="upload-dropzone">
                      <label>Upload boundary (.KML / .KMZ)</label>
                      <input type="file" accept=".kml,.kmz" onChange={handleFileUpload} />
                      <span>{polygonCoords?.length ? `${polygonCoords.length} boundary points loaded` : 'The first polygon in the file becomes the active parcel boundary.'}</span>
                      {uploadedFileName && (
                        <div className="upload-meta-row">
                          <span>{uploadedFileName}</span>
                        </div>
                      )}

                    </div>
                  )}

                  <div className="input-group">
                    <label className="label-wrap"><Maximize size={16} /> Area (Acres)</label>
                    <input type="number" step="any" required className="input-field" value={area} onChange={(e) => setArea(e.target.value)} />
                  </div>

                </div>
              </details>

              <details className="accordion-card">
                <summary className="accordion-header">
                  <div style={{display:'flex', alignItems:'center', gap:'0.75rem'}}>
                    <span className="section-step">Step 2</span>
                    <h3 style={{margin:0}}><Layers size={18} /> Configure analysis</h3>
                  </div>
                  <ChevronDown size={18} className="chevron" />
                </summary>
                <div className="accordion-content">
                  <div className="input-group">
                    <label className="label-wrap"><span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Zap size={15} /> Grid Substation (GSS)</span></label>
                    <span className="field-hint">Run a scan to find nearby substations, or enter a manual coordinate pair if you already have one.</span>
                    <div className="mode-toggle-inline">
                      <label><input type="radio" value="auto" checked={substationMode==='auto'} onChange={()=>setSubstationMode('auto')} /> Auto</label>
                      <label><input type="radio" value="manual" checked={substationMode==='manual'} onChange={()=>setSubstationMode('manual')} /> Manual</label>
                    </div>
                    {substationMode === 'auto' ? (
                      <>
                        <div className="inline-field-row">
                          <div className="input-group" style={{ marginBottom: 0, flex: 1 }}>
                            <label className="label-wrap">Scan radius (km)</label>
                            <input
                              type="number"
                              min="1"
                              step="1"
                              className="input-field"
                              value={gssRadiusKm}
                              onChange={(e) => setGssRadiusKm(e.target.value)}
                              placeholder="20"
                            />
                          </div>
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => fetchNearbyGss(lat, lon, gssRadiusKm)}
                            disabled={isFetchingGss || !lat || !lon}
                            style={{ alignSelf: 'end' }}
                          >
                            {isFetchingGss ? <><Loader size={12} className="spin-inline" /> Scanning...</> : 'Run GSS Scan'}
                          </button>
                        </div>
                        <span className="field-hint">Enter a radius like 10 or 20 km. The scan will use that exact distance.</span>
                        <div className="inline-field-row">
                          <select className="input-field" value={selectedGss} onChange={(e) => setSelectedGss(e.target.value)} disabled={nearbyGss.length === 0 || isFetchingGss}>
                            {nearbyGss.length === 0 ? <option value="">No GSS scan run yet</option> : nearbyGss.map((g, i) => (
                              <option key={i} value={g.name}>{g.name} [{g.voltage||'??'}kV] - {g.distance_km}km</option>
                            ))}
                          </select>
                        </div>
                        <span className="field-hint">
                          {nearbyGss.length > 0
                            ? `Found ${nearbyGss.length} nearby substations.`
                            : 'The scan will populate this list once you run it.'}
                        </span>
                        {gssScanStatus && (
                          <span className="field-hint">{gssScanStatus}</span>
                        )}
                      </>
                    ) : (
                      <input type="text" className="input-field" placeholder="Paste GSS Lat, Lon..." value={manualGss} onChange={handleManualGssChange} />
                    )}
                  </div>

                  <div className="gss-auto-finder-card">
                    <div className="gss-auto-finder-header">
                      <div>
                        <h4 style={{ margin: 0 }}>Auto GSS Finder within 25 km</h4>
                        <span className="field-hint">Automatically finds nearby substations after KML upload or coordinate entry.</span>
                      </div>
                      <button type="button" className="btn-secondary" onClick={fetchAutoGssFinder} disabled={autoGssLoading || !lat || !lon}>
                        {autoGssLoading ? <><Loader size={12} className="spin-inline" /> Finding...</> : 'Refresh'}
                      </button>
                    </div>
                    <div className="gss-filter-row">
                      <label className="label-wrap">
                        Distance
                        <select className="input-field" value={autoGssDistanceFilter} onChange={(e) => setAutoGssDistanceFilter(e.target.value)}>
                          <option value="5">Within 5 km</option>
                          <option value="10">Within 10 km</option>
                          <option value="15">Within 15 km</option>
                          <option value="25">Within 25 km</option>
                        </select>
                      </label>
                      <label className="label-wrap">
                        Voltage
                        <select className="input-field" value={autoGssVoltageFilter} onChange={(e) => setAutoGssVoltageFilter(e.target.value)}>
                          <option value="all">All</option>
                          <option value="132kv">132kV</option>
                          <option value="220kv">220kV</option>
                          <option value="400kv">400kV</option>
                          <option value="unknown">Unknown</option>
                        </select>
                      </label>
                    </div>
                    <div className="gss-summary-row">
                      <div className="summary-chip"><Shield size={14} /> {autoGssSummary?.nearest_gss_name || 'No GSS found'}</div>
                      <div className="summary-chip"><MapPin size={14} /> {autoGssSummary?.distance_km ? `${autoGssSummary.distance_km} km` : 'Unavailable'}</div>
                      <div className="summary-chip"><Zap size={14} /> {autoGssSummary?.voltage_level || 'unknown'}</div>
                    </div>
                    <div className="field-hint">{autoGssRemark}</div>
                    <div className="field-hint">Next action: {autoGssSummary?.next_action || 'verify bay availability and STU connectivity status'}</div>
                    {autoGssError && <div className="field-error">{autoGssError}</div>}
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        if (!autoGssSummary?.nearest_gss_name) return;
                        setIntelTargetGss(autoGssSummary.nearest_gss_name);
                        setCustomPrompt(
                          `Auto GSS Finder Summary\n` +
                          `Nearest GSS: ${autoGssSummary.nearest_gss_name}\n` +
                          `Distance: ${autoGssSummary.distance_km ?? 'Unavailable'} km\n` +
                          `Voltage: ${autoGssSummary.voltage_level || 'unknown'}\n` +
                          `Risk: ${autoGssSummary.risk_remark}\n` +
                          `Next action: ${autoGssSummary.next_action || 'verify bay availability and STU connectivity status'}`
                        );
                      }}
                      disabled={!autoGssSummary?.nearest_gss_name}
                    >
                      Generate GSS Feasibility Summary
                    </button>
                  </div>

                  <div className="gss-results-table">
                    <div className="gss-results-table-header">
                      <h4 style={{ margin: 0 }}>Nearby GSS Results</h4>
                      <span className="field-hint">{filteredAutoGssResults.length} result(s) shown</span>
                    </div>
                    <div className="gss-results-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Latitude</th>
                            <th>Longitude</th>
                            <th>Voltage</th>
                            <th>Distance (km)</th>
                            <th>Source</th>
                            <th>Confidence</th>
                            <th>Verification</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredAutoGssResults.length > 0 ? filteredAutoGssResults.map((item, idx) => (
                            <tr key={`${item.name}-${idx}`}>
                              <td>{item.name}</td>
                              <td>{formatSummaryNumber(item.lat)}</td>
                              <td>{formatSummaryNumber(item.lon)}</td>
                              <td>{item.voltage_level || 'unknown'}</td>
                              <td>{formatSummaryNumber(item.distance_km)}</td>
                              <td>{item.data_source}</td>
                              <td>{item.confidence_level}</td>
                              <td>{item.verification_status}</td>
                            </tr>
                          )) : (
                            <tr>
                              <td colSpan="8">{autoGssLoading ? 'Searching for nearby GSS...' : 'No nearby GSS found.'}</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <LayerControlPanel lat={lat} lon={lon} area={area} onLayersChange={handleLayersChange} />
                </div>
              </details>


            </form>
</div>

        </div>

        <div className="resize-handle left" onMouseDown={() => { setIsResizingLeft(true); document.body.style.cursor = 'col-resize'; }} />
          </div>

        <div className="gss-map-container">
          <div className="map-status-bar">
            <div className="map-status-pill"><MapPin size={14} /> {lat}, {lon}</div>
            <div className="map-status-pill"><Maximize size={14} /> {area} acres</div>
            <div className={`map-status-pill ${revenueMapActive ? 'active' : ''}`}><Layers size={14} /> {revenueMapActive ? 'Revenue overlay on' : 'Base imagery only'}</div>
            <div className={`map-status-pill ${selectedGssDistance ? 'active' : ''}`}><Zap size={14} /> {selectedGssDistance ? `${formatSummaryNumber(selectedGssDistance)} km to GSS` : 'GSS pending'}</div>
            <div className={`map-status-pill ${transmissionLines.length > 0 ? 'active' : ''}`} style={{ backgroundColor: transmissionLines.length > 0 ? '#065f46' : '' }}>
              {isFetchingLines ? (
                <><Loader size={14} className="animate-spin" /> Scanning Transmission Grid...</>
              ) : (
                <><Zap size={14} color="#4ade80" /> {transmissionLines.length} Power Lines Detected{transmissionLines.length > 0 ? ` · ${transmissionLineVoltageSummary}` : ''}{transmissionLineSource ? ` · ${transmissionLineSource}` : ''}</>
              )}
            </div>
          </div>
          <MapContainer 
            center={[parseFloat(lat) || 27.0238, parseFloat(lon) || 71.9213]} 
            zoom={13} 
            style={{ height: '100%', width: '100%', zIndex: 0 }}
            zoomControl={false}
          >
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
            />
            <MapEvents />
            
            <FeatureGroup>
              <EditControl
                position='topright'
                onCreated={(e) => {
                  const layer = e.layer;
                  if (layer instanceof L.Polygon) {
                    const coords = layer.getLatLngs()[0].map(latlng => [latlng.lat, latlng.lng]);
                    setPolygonCoords(coords);
                  }
                }}
                onEdited={(e) => {
                  e.layers.eachLayer((layer) => {
                    if (layer instanceof L.Polygon) {
                      const coords = layer.getLatLngs()[0].map(latlng => [latlng.lat, latlng.lng]);
                      setPolygonCoords(coords);
                    }
                  });
                }}
                onDeleted={() => setPolygonCoords(null)}
                draw={{
                  polyline: false,
                  circle: false,
                  rectangle: false,
                  circlemarker: false,
                  marker: false,
                }}
              />
            </FeatureGroup>

            <MapController lat={lat} lon={lon} area={area} polygonCoords={polygonCoords} />

            {/* Transmission Lines Layer - 3-Tier Fused Visualization */}
            {transmissionLines && transmissionLines.length > 0 && transmissionLines.map((line) => {
              // Color and Style by Tier
              // Tier 1: Verified (Solid)
              // Tier 2: Probable (Dashed)
              // Tier 3: Inferred (Dotted)
              const tierStyles = {
                'Verified': { color: '#4ade80', dashArray: null, weight: 10, opacity: 0.95 },
                'Probable': { color: '#22d3ee', dashArray: '10, 10', weight: 7, opacity: 0.8 },
                'Inferred': { color: '#fbbf24', dashArray: '2, 6', weight: 4, opacity: 0.6 }
              };
              
              const style = tierStyles[line.tier] || tierStyles['Inferred'];
              
              return (
                <Polyline 
                  key={`line-tiered-${line.id}`}
                  positions={line.coordinates}
                  pathOptions={{ 
                    ...style,
                    lineJoin: 'round',
                    pane: 'overlayPane'
                  }}
                >
                  <Popup>
                    <div style={{ padding: '8px', minWidth: '220px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <strong style={{ color: style.color }}>{line.tier} Grid Link</strong>
                        <span style={{ fontSize: '10px', background: '#334155', color: '#fff', padding: '1px 4px', borderRadius: '4px' }}>
                          {(line.confidence_score * 100).toFixed(0)}% Match
                        </span>
                      </div>
                      
                      <div style={{ fontSize: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '6px' }}>
                        <p style={{ margin: '2px 0' }}><strong>Voltage:</strong> {line.voltage_kv ? `${line.voltage_kv}kV` : 'Unknown'}</p>
                        <p style={{ margin: '2px 0' }}><strong>Operator:</strong> {line.operator}</p>
                        <p style={{ margin: '2px 0' }}><strong>Source:</strong> {line.source}</p>
                        <p style={{ margin: '8px 0 2px 0', fontSize: '11px', color: '#64748b', fontStyle: 'italic' }}>
                          <strong>Reasoning:</strong> {line.detection_reason}
                        </p>
                      </div>
                      <div style={{ marginTop: '8px', fontSize: '9px', color: '#94a3b8', borderTop: '1px dotted #e2e8f0', pt: '4px' }}>
                        System ID: {line.id}
                      </div>
                    </div>
                  </Popup>
                </Polyline>
              );
            })}

            {/* Display the active site area */}
            {polygonCoords && polygonCoords.length > 0 ? (
              <Polygon 
                positions={polygonCoords} 
                pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.2, weight: 3 }} 
              />
            ) : (lat && lon && area && !isNaN(parseFloat(area)) && (
              <Circle 
                center={[parseFloat(lat), parseFloat(lon)]}
                radius={Math.sqrt((parseFloat(area) * 4046.86) / Math.PI)}
                pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.1, weight: 2, dashArray: '5, 5' }}
              />
            ))}

            {/* Analytical map overlays */}
            {activeTileLayers.map(layer => (
              <TileLayer key={layer.id} url={layer.tileUrl} opacity={0.75} />
            ))}

            {/* GSS Markers from Auto Finder */}
            {filteredAutoGssResults.map((gss, idx) => (
              <Marker 
                key={`gss-auto-${idx}`} 
                position={[gss.lat, gss.lon]}
                icon={L.divIcon({
                  className: 'custom-gss-icon',
                  html: `<div class="gss-marker-ring ${gss.voltage_level?.toLowerCase().includes('400') ? 'v400' : gss.voltage_level?.toLowerCase().includes('220') ? 'v220' : 'v132'}"></div>`,
                  iconSize: [24, 24]
                })}
              >
                <Tooltip permanent direction="top" offset={[0, -10]} className="gss-label-tooltip">
                  {gss.name} [{gss.voltage_level || '??'}]
                </Tooltip>
                <Popup>
                  <div className="map-popup-custom">
                    <h4 style={{ margin: '0 0 8px 0', color: '#10b981' }}>{gss.name}</h4>
                    <p style={{ margin: '4px 0' }}><strong>Voltage:</strong> {gss.voltage_level}</p>
                    <p style={{ margin: '4px 0' }}><strong>Distance:</strong> {gss.distance_km} km</p>
                    <p style={{ margin: '4px 0' }}><strong>Source:</strong> {gss.data_source || 'Auto Finder'}</p>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* GSS Markers from Manual Scan */}
            {/* GSS Markers from Manual Scan */}
            {nearbyGss.map((g, i) => (
              <Marker 
                key={`manual-${i}`} 
                position={[g.lat, g.lon]}
                icon={L.divIcon({
                  className: 'custom-gss-icon',
                  html: `<div class="gss-marker-ring v132"></div>`,
                  iconSize: [20, 20]
                })}
              >
                <Tooltip direction="top" offset={[0, -10]}>
                  {g.name} (Manual)
                </Tooltip>
                <Popup>
                  <strong>{g.name}</strong><br/>
                  Distance: {g.distance_km} km<br/>
                  Voltage: {g.voltage || 'unknown'}<br/>
                  Source: Manual Scan
                </Popup>
              </Marker>
            ))}

            {lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon)) && (
              <Marker 
                position={[parseFloat(lat), parseFloat(lon)]}
                icon={L.icon({
                  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
                  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
                  iconSize: [25, 41],
                  iconAnchor: [12, 41],
                  popupAnchor: [1, -34],
                })}
              >
                <Popup className="site-popup">
                  <div className="popup-content">
                    <h4 style={{ margin: '0 0 8px 0', color: '#38bdf8' }}>Parcel Scout Intelligence</h4>
                    {isFetchingLoc ? (
                      <p><Loader size={14} className="animate-spin" /> Fetching location details...</p>
                    ) : propertyInfo ? (
                      <>
                        <p><strong>Address:</strong> {propertyInfo.full_address}</p>
                        <p><strong>Area:</strong> {area} Acres (~{(parseFloat(area)/5).toFixed(1)} MW)</p>
                        <p><strong>District:</strong> {propertyInfo.district || 'N/A'}</p>
                      </>
                    ) : (
                      <p>Location data unavailable for these coordinates.</p>
                    )}
                    <button onClick={() => handleAnalyze()} className="btn-primary" style={{ padding: '6px', fontSize: '12px', marginTop: '10px' }}>
                      Run Full Feasibility Analysis
                    </button>
                  </div>
                </Popup>
              </Marker>
            )}

            {/* Nearby Places Markers (Villages, Towns, Landmarks) */}
            {nearbyPlaces.map((place, idx) => (
              <CircleMarker
                key={`place-${idx}`}
                center={[place.lat, place.lon]}
                radius={4}
                pathOptions={{ color: '#ffffff', fillColor: '#8b5cf6', fillOpacity: 0.9, weight: 1 }}
              >
                <Popup>
                  <strong>{place.name}</strong><br/>
                  Type: {place.type}<br/>
                  Distance: {place.distance_km} km
                </Popup>
              </CircleMarker>
            ))}

            {/* Path to selected GSS */}
            {selectedGssPos && (
              <Polyline 
                positions={[[parseFloat(lat), parseFloat(lon)], [selectedGssPos[0], selectedGssPos[1]]]} 
                pathOptions={{ color: '#38bdf8', weight: 4, dashArray: '5, 5' }} 
              />
            )}
          </MapContainer>
        </div>

        <div className="resize-handle right" onMouseDown={() => { setIsResizingRight(true); document.body.style.cursor = 'col-resize'; }} />

        {isRightMinimized && (
          <button type="button" className="floating-reopen-btn floating-reopen-btn--right" onClick={() => setIsRightMinimized(false)}>
            <MessageSquarePlus size={16} /> Open report
          </button>
        )}
        <div className={`gss-analysis-panel ${isRightMinimized ? 'minimized' : ''}`} style={{ width: isRightMinimized ? '0' : rightWidth + 'px', minWidth: isRightMinimized ? '0' : 'unset', maxWidth: isRightMinimized ? '0' : 'unset' }}>
          <div className="analysis-panel-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <MessageSquarePlus size={18} /> {!isRightMinimized && "Report Builder"}
              </div>
              <button onClick={() => setIsRightMinimized(!isRightMinimized)} className="minimize-toggle-btn" title={isRightMinimized ? "Expand" : "Minimize"}>
                {isRightMinimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
              </button>
            </div>
          </div>
          <div className="analysis-panel-scroll" style={{ opacity: isRightMinimized ? 0 : 1, pointerEvents: isRightMinimized ? 'none' : 'auto', minWidth: isRightMinimized ? '0' : '400px' }}>

            <LandDiscoveryReportPanel
              area={area}
              loading={loading}
              loadingMessage={loadingMessage}
              report={report}
              error={error}
              revenueWarning={revenueWarning}
              selectedGssDistance={selectedGssDistance}
              reportRef={reportRef}
              onRunAnalysis={handleAnalyze}
              onStopAnalysis={handleStopAnalysis}
              onExpandReport={() => setReportExpanded(true)}
              onDownloadPdf={handleDownloadPDF}
              intelTargetGss={intelTargetGss}
              setIntelTargetGss={setIntelTargetGss}
              intelText={intelText}
              setIntelText={setIntelText}
              onSubmitIntel={submitIntelligence}
              isSubmittingIntel={isSubmittingIntel}
              intelStatus={intelStatus}
              feedbackText={feedbackText}
              setFeedbackText={setFeedbackText}
              onSubmitFeedback={submitFeedback}
              isSubmittingFeedback={isSubmittingFeedback}
              feedbackSuccess={feedbackSuccess}
              hasInputs={Boolean(lat && lon)}
            />
          </div>
        </div>

        {reportExpanded && report && (
          <div className="ld-report-expanded">
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginBottom: '1.5rem', position: 'sticky', top: 0, zIndex: 10, background: 'rgba(15, 23, 42, 0.98)', padding: '0.5rem 0' }}>
              <button onClick={handleDownloadPDF} className="btn-primary" style={{ width: 'auto', padding: '0.6rem 1rem' }}>
                <Download size={16} /> Download PDF
              </button>
              <button onClick={() => setReportExpanded(false)} className="btn-secondary" style={{ padding: '0.6rem 1rem' }}>
                <Minimize2 size={16} /> Close Full Report
              </button>
            </div>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        )}
      </div>
    ) : null}



    </>
  );
}

export default LandDiscoveryAgent;
