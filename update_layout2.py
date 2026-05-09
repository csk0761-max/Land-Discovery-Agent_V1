import re
import sys

with open("frontend/src/LandDiscoveryAgent.jsx", "r") as f:
    content = f.read()

start_marker = '<div className="glass-card insight-strip-card">'
start_idx = content.find(start_marker)

# Finding the end marker: `</div>` for `{plotInfo && ...}` inside `.sidebar-scrollable`
# A reliable way is to find the end of `plotInfo && (` block, then the matching `</div>` for the sidebar-scrollable is just after it, before `{!isMobileLayout && isLeftMinimized && (` or before the `resize-handle` div.
end_marker = '</div>\n          {!isMobileLayout && isLeftMinimized'
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers!")
    print(f"start_idx: {start_idx}, end_idx: {end_idx}")
    sys.exit(1)

# we need to re-generate the block. We will just use the string.
original_block = content[start_idx:end_idx]

# I need to pull out the chunks from the original block.
# Actually, I can just replace the whole block since the logic hasn't changed.
new_block = """<form onSubmit={handleAnalyze} className="analysis-form">
              <details className="accordion-card" open>
                <summary className="accordion-header">
                  <div style={{display:'flex', alignItems:'center', gap:'0.75rem'}}>
                    <span className="section-step">Step 1</span>
                    <h3 style={{margin:0}}><Compass size={18} /> Define site</h3>
                  </div>
                  <ChevronDown size={18} className="chevron" />
                </summary>
                <div className="accordion-content">
                  <div className="signal-warning">
                    Revenue and ownership overlays in this build are demo aids. Verify khasra, land class, and owners on the source portal before using them operationally.
                  </div>

                  <div className="quick-insights-grid">
                    {analysisSummary.map((item) => (
                      <div key={item.label} className={`quick-insight-card tone-${item.tone}`}>
                        <span className="quick-insight-label">{item.label}</span>
                        <strong>{item.value}</strong>
                      </div>
                    ))}
                  </div>

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
                          <span>{uploadedSurveyNumbers.length ? `${uploadedSurveyNumbers.length} survey numbers detected` : 'No explicit survey numbers found in file metadata'}</span>
                        </div>
                      )}
                      {polygonCoords?.length > 2 && (
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => requestOwnershipDetails(polygonCoords, uploadedSurveyNumbers)}
                          disabled={isFetchingOwnership || (propertyInfo?.state === 'Chhattisgarh' && !cgAdminSelection.village_code)}
                        >
                          {isFetchingOwnership ? <><Loader size={12} className="spin-inline" /> Generating ownership...</> : 'Generate ownership details'}
                        </button>
                      )}
                    </div>
                  )}

                  <div className="site-overview-grid">
                    <div className="overview-chip">
                      <Radar size={14} />
                      <span>{inputType === 'manual' ? 'Coordinate mode' : 'Boundary upload mode'}</span>
                    </div>
                    <div className="overview-chip">
                      <MapIcon size={14} />
                      <span>{propertyInfo?.state || 'State pending'}</span>
                    </div>
                    <div className="overview-chip">
                      <Zap size={14} />
                      <span>{selectedGssDistance ? `${selectedGssDistance} km to target GSS` : 'GSS distance pending'}</span>
                    </div>
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
                    <span className="field-hint">Pick the nearest substation automatically, or enter a manual coordinate pair if you already have one.</span>
                    <div className="mode-toggle-inline">
                      <label><input type="radio" value="auto" checked={substationMode==='auto'} onChange={()=>setSubstationMode('auto')} /> Auto</label>
                      <label><input type="radio" value="manual" checked={substationMode==='manual'} onChange={()=>setSubstationMode('manual')} /> Manual</label>
                    </div>
                    {substationMode === 'auto' ? (
                      <div className="inline-field-row">
                        <select className="input-field" value={selectedGss} onChange={(e) => setSelectedGss(e.target.value)} disabled={nearbyGss.length === 0}>
                          {nearbyGss.length === 0 ? <option value="">No GSS fetched yet</option> : nearbyGss.map((g, i) => (
                            <option key={i} value={g.name}>{g.name} [{g.voltage||'??'}kV] - {g.distance_km}km</option>
                          ))}
                        </select>
                        <button type="button" onClick={fetchNearbyGss} className="btn-secondary" disabled={isFetchingGss}>
                          {isFetchingGss ? <Loader size={12} className="spin-inline" /> : <Search size={12} />} Scan
                        </button>
                      </div>
                    ) : (
                      <input type="text" className="input-field" placeholder="Paste GSS Lat, Lon..." value={manualGss} onChange={handleManualGssChange} />
                    )}
                  </div>

                  <div className="input-group">
                    <label className="label-wrap"><Maximize size={16} /> Area (Acres)</label>
                    <input type="number" step="any" required className="input-field" value={area} onChange={(e) => setArea(e.target.value)} />
                  </div>
                  
                  <div className="input-group">
                    <label className="label-wrap"><MessageSquarePlus size={16} /> Analyst focus</label>
                    <textarea
                      className="input-field"
                      rows="3"
                      placeholder="Optional: ask for transmission feasibility, environmental caveats, revenue risks, or a decision memo."
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      style={{ resize: 'vertical' }}
                    />
                  </div>

                  <div className="overlay-actions">
                    <button
                      type="button"
                      className={`btn-secondary ${revenueMapActive ? 'overlay-active' : ''}`}
                      onClick={() => {
                        const nextState = !revenueMapActive;
                        setRevenueMapActive(nextState);
                        if (nextState) {
                          fetchWmsConfig(propertyInfo?.state || 'Rajasthan');
                        }
                      }}
                    >
                      <FileWarning size={14} /> {revenueMapActive ? 'Revenue overlay active' : 'Enable revenue overlay'}
                    </button>
                    <a className="overlay-link" href={portalInfo.url} target="_blank" rel="noreferrer">
                      Source portal: {portalInfo.name}
                    </a>
                  </div>

                  <LayerControlPanel lat={lat} lon={lon} area={area} onLayersChange={handleLayersChange} />
                </div>
              </details>

              <details className="accordion-card">
                <summary className="accordion-header">
                  <div style={{display:'flex', alignItems:'center', gap:'0.75rem'}}>
                    <span className="section-step">Context</span>
                    <h3 style={{margin:0}}><MapIcon size={18} /> Site snapshot</h3>
                  </div>
                  <ChevronDown size={18} className="chevron" />
                </summary>
                <div className="accordion-content">
                  <div className="detail-matrix">
                    <div><span>Coordinates</span><strong>{lat}, {lon}</strong></div>
                    <div><span>Area</span><strong>{area} acres</strong></div>
                    <div><span>District</span><strong>{propertyInfo?.district || 'Pending lookup'}</strong></div>
                    <div><span>State</span><strong>{selectedState}</strong></div>
                    <div><span>Nearest GSS</span><strong>{selectedGssLabel}</strong></div>
                    <div><span>Distance</span><strong>{selectedGssDistance ? `${selectedGssDistance} km` : 'Pending'}</strong></div>
                  </div>
                  
                  {plotInfo && (
                    <div style={{ borderTop: '4px solid #f59e0b', paddingTop: '1rem', marginTop: '1rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                        <div style={{ fontWeight: 600, color: '#fbbf24' }}>Revenue Overlay Details</div>
                        <div style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>{plotInfo.status || 'No status'}</div>
                      </div>
                      {plotInfo.warning && (
                        <div style={{ fontSize: '0.8rem', color: '#fca5a5', background: 'rgba(127, 29, 29, 0.25)', border: '1px solid rgba(248, 113, 113, 0.35)', borderRadius: '8px', padding: '0.75rem', marginBottom: '0.75rem' }}>
                          {plotInfo.warning}
                        </div>
                      )}
                      <div style={{ fontSize: '0.85rem', color: '#cbd5e1', display: 'grid', gap: '0.35rem' }}>
                        <div>Portal: <span style={{ color: '#1e293b' }}>{plotInfo.portal || 'Unknown'}</span></div>
                        {plotInfo.khasra_no && <div>Khasra: <span style={{ color: '#1e293b' }}>{plotInfo.khasra_no}</span></div>}
                        {Array.isArray(plotInfo.owners) && plotInfo.owners.length > 0 && (
                          <div>Owners: <span style={{ color: '#1e293b' }}>{plotInfo.owners.join(', ')}</span></div>
                        )}
                        {plotInfo.land_type && <div>Land Type: <span style={{ color: '#1e293b' }}>{plotInfo.land_type}</span></div>}
                      </div>
                    </div>
                  )}
                </div>
              </details>
            </form>
"""

new_content = content[:start_idx] + new_block + content[end_idx:]

with open("frontend/src/LandDiscoveryAgent.jsx", "w") as f:
    f.write(new_content)
print("Updated successfully")
