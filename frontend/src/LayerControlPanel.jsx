import React, { useState, useCallback } from 'react';
import { Layers, Eye, EyeOff, FileText, Loader, Camera, X } from 'lucide-react';
import './LayerControlPanel.css';

const AVAILABLE_LAYERS = [
    {
        id: 'land_cover',
        name: 'Land Cover',
        description: 'ESA WorldCover 10m Classification',
        colorChip: 'linear-gradient(90deg, #006400, #ffff4c, #fa0000, #b4b4b4)',
    },
    {
        id: 'slope',
        name: 'Terrain Slope',
        description: 'USGS SRTM Slope (0°–30°)',
        colorChip: 'linear-gradient(90deg, #ffffd9, #41b6c4, #081d58)',
    },
    {
        id: 'surface_water',
        name: 'Surface Water',
        description: 'JRC Historical Water Occurrence',
        colorChip: 'linear-gradient(90deg, #ffffff, #4499ee, #003399)',
    },
    {
        id: 'ndvi',
        name: 'Vegetation (NDVI)',
        description: 'MODIS Vegetation Index 2023',
        colorChip: 'linear-gradient(90deg, #d73027, #ffffbf, #1a9850)',
    },
    {
        id: 'nighttime_lights',
        name: 'Nighttime Lights',
        description: 'NOAA VIIRS Electrification Proxy',
        colorChip: 'linear-gradient(90deg, #000000, #aaaa00, #ff8800)',
    },
    {
        id: 'solar_ghi',
        name: 'Solar GHI',
        description: 'ECMWF ERA5 Solar Irradiance',
        colorChip: 'linear-gradient(90deg, #313695, #fdae61, #a50026)',
    },
    {
        id: 'protected_areas',
        name: 'Protected Areas',
        description: 'WCMC WDPA Conservation Zones',
        colorChip: 'linear-gradient(90deg, #ff4444, #ff444480)',
    },
];

const INIT_STATE = Object.fromEntries(
    AVAILABLE_LAYERS.map(l => [l.id, {
        active: false,
        inReport: false,
        loading: false,
        thumbLoading: false,
        tileUrl: null,
        attribution: '',
        thumbnailUrl: null,
        thumbnailLabel: '',
        error: null,
    }])
);

export default function LayerControlPanel({ lat, lon, area, onLayersChange }) {
    const [isOpen, setIsOpen] = useState(false);
    const [layerStates, setLayerStates] = useState(INIT_STATE);

    const notifyParent = useCallback((states) => {
        const activeLayers = Object.entries(states)
            .filter(([, s]) => s.active && s.tileUrl)
            .map(([id, s]) => ({ id, tileUrl: s.tileUrl, attribution: s.attribution }));
        const reportLayers = Object.entries(states)
            .filter(([, s]) => s.inReport)
            .map(([id]) => id);
        // Build thumbnail map: only layers that are inReport AND have a thumbnailUrl
        const layerThumbnails = Object.fromEntries(
            Object.entries(states)
                .filter(([, s]) => s.inReport && s.thumbnailUrl)
                .map(([id, s]) => [id, s.thumbnailUrl])
        );
        onLayersChange(activeLayers, reportLayers, layerThumbnails);
    }, [onLayersChange]);

    const toggleLayer = useCallback(async (layerId) => {
        const current = layerStates[layerId];
        if (current.active) {
            setLayerStates(prev => {
                const updated = { ...prev, [layerId]: { ...prev[layerId], active: false, tileUrl: null } };
                notifyParent(updated);
                return updated;
            });
            return;
        }
        setLayerStates(prev => ({ ...prev, [layerId]: { ...prev[layerId], loading: true, error: null } }));
        try {
            const params = new URLSearchParams({ lat, lon, area_acres: area });
            const res = await fetch(`http://localhost:8000/layers/${layerId}/tile-url?${params}`);
            const data = await res.json();
            if (!res.ok || data.detail) throw new Error(data.detail || 'Failed to load layer');
            setLayerStates(prev => {
                const updated = {
                    ...prev,
                    [layerId]: { ...prev[layerId], active: true, loading: false, tileUrl: data.tileUrl, attribution: data.attribution, error: null }
                };
                notifyParent(updated);
                return updated;
            });
        } catch (err) {
            setLayerStates(prev => ({ ...prev, [layerId]: { ...prev[layerId], loading: false, error: err.message } }));
        }
    }, [layerStates, lat, lon, area, notifyParent]);

    const toggleInReport = useCallback(async (layerId) => {
        const current = layerStates[layerId];
        const newInReport = !current.inReport;

        if (!newInReport) {
            // Unchecking — remove from report, clear thumbnail
            setLayerStates(prev => {
                const updated = { ...prev, [layerId]: { ...prev[layerId], inReport: false, thumbnailUrl: null } };
                notifyParent(updated);
                return updated;
            });
            return;
        }

        // Checking — fetch thumbnail if not already fetched
        setLayerStates(prev => ({ ...prev, [layerId]: { ...prev[layerId], inReport: true, thumbLoading: true } }));
        try {
            const params = new URLSearchParams({ lat, lon, area_acres: area });
            const res = await fetch(`http://localhost:8000/layers/${layerId}/thumbnail?${params}`);
            const data = await res.json();
            if (!res.ok || data.detail) throw new Error(data.detail || 'Failed to fetch thumbnail');
            setLayerStates(prev => {
                const updated = {
                    ...prev,
                    [layerId]: { ...prev[layerId], inReport: true, thumbLoading: false, thumbnailUrl: data.thumbnailUrl, thumbnailLabel: data.label }
                };
                notifyParent(updated);
                return updated;
            });
        } catch (err) {
            // Still mark in report, just without thumbnail
            setLayerStates(prev => {
                const updated = { ...prev, [layerId]: { ...prev[layerId], inReport: true, thumbLoading: false, thumbnailUrl: null } };
                notifyParent(updated);
                return updated;
            });
        }
    }, [layerStates, lat, lon, area, notifyParent]);

    const activeCount = Object.values(layerStates).filter(s => s.active).length;
    const reportCount = Object.values(layerStates).filter(s => s.inReport).length;

    return (
        <div className="layer-panel glass-card">
            <div className="layer-panel-header" onClick={() => setIsOpen(!isOpen)}>
                <div className="layer-panel-title">
                    <Layers size={18} color="var(--primary)" />
                    <span>GEE Data Layers</span>
                    <div className="layer-badges">
                        {activeCount > 0 && <span className="badge-active-count">{activeCount} live</span>}
                        {reportCount > 0 && <span className="badge-report-count">{reportCount} in report</span>}
                    </div>
                </div>
                <span className={`panel-chevron ${isOpen ? 'open' : ''}`}>▾</span>
            </div>

            {isOpen && (
                <div className="layer-list">
                    <p className="layer-list-hint">
                        <Eye size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> Toggle map overlay.&nbsp;
                        <FileText size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> Include in AI report with snapshot.
                    </p>
                    {AVAILABLE_LAYERS.map(layer => {
                        const state = layerStates[layer.id];
                        return (
                            <div key={layer.id} className={`layer-item ${state.active ? 'layer-item--active' : ''} ${state.inReport ? 'layer-item--in-report' : ''}`}>
                                {/* Main row */}
                                <div className="layer-row">
                                    <div className="layer-color-chip" style={{ background: layer.colorChip }} />
                                    <div className="layer-info">
                                        <span className="layer-name">{layer.name}</span>
                                        <span className="layer-desc">{layer.description}</span>
                                        {state.error && <span className="layer-error">⚠ {state.error}</span>}
                                    </div>
                                    <div className="layer-controls">
                                        {/* Report checkbox */}
                                        <button
                                            className={`layer-report-btn ${state.inReport ? 'active' : ''}`}
                                            onClick={() => toggleInReport(layer.id)}
                                            disabled={state.thumbLoading}
                                            title={state.inReport ? 'Remove from AI Report' : 'Add to AI Report with map snapshot'}
                                        >
                                            {state.thumbLoading ? (
                                                <Loader size={13} className="spin-icon" />
                                            ) : (
                                                <FileText size={13} />
                                            )}
                                        </button>

                                        {/* Map toggle */}
                                        <button
                                            className={`layer-toggle-btn ${state.active ? 'active' : ''}`}
                                            onClick={() => toggleLayer(layer.id)}
                                            disabled={state.loading}
                                            title={state.active ? 'Hide from map' : 'Show on map'}
                                        >
                                            {state.loading ? (
                                                <Loader size={13} className="spin-icon" />
                                            ) : state.active ? (
                                                <Eye size={13} />
                                            ) : (
                                                <EyeOff size={13} />
                                            )}
                                        </button>
                                    </div>
                                </div>

                                {/* Thumbnail preview when in report */}
                                {state.inReport && state.thumbnailUrl && (
                                    <div className="layer-thumbnail-preview">
                                        <div className="thumb-header">
                                            <Camera size={11} />
                                            <span>{state.thumbnailLabel || layer.name} — Map Snapshot</span>
                                            <span className="thumb-badge">📎 Pinned to Report</span>
                                        </div>
                                        <img
                                            src={state.thumbnailUrl}
                                            alt={`${layer.name} map snapshot`}
                                            className="thumb-img"
                                        />
                                    </div>
                                )}

                                {state.inReport && state.thumbLoading && (
                                    <div className="layer-thumbnail-loading">
                                        <Loader size={14} className="spin-icon" />
                                        <span>Capturing map snapshot from GEE…</span>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
