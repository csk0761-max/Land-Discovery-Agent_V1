import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download, FileText, Layers, Loader, Maximize2, MessageSquarePlus, Shield } from 'lucide-react';

export default function LandDiscoveryReportPanel({
  area,
  loading,
  loadingMessage,
  report,
  error,
  revenueWarning,
  selectedGssDistance,
  reportRef,
  onRunAnalysis,
  onStopAnalysis,
  onExpandReport,
  onDownloadPdf,
  intelTargetGss,
  setIntelTargetGss,
  intelText,
  setIntelText,
  onSubmitIntel,
  isSubmittingIntel,
  intelStatus,
  feedbackText,
  setFeedbackText,
  onSubmitFeedback,
  isSubmittingFeedback,
  feedbackSuccess,
  hasInputs,
}) {
  return (
    <div className="gss-analysis-panel">
      <div className="analysis-panel-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MessageSquarePlus size={18} /> Report workspace
          </div>
          <span className="report-panel-badge">Decision memo</span>
        </div>
      </div>

      <div className="analysis-panel-scroll">
        <p className="report-panel-intro">
          Generate an investment-grade memorandum with executive summary, risk ranking, and recommended next steps.
        </p>
        <button type="button" onClick={onRunAnalysis} className="btn-primary" disabled={loading}>
          {loading ? <><div className="loader" style={{ margin: '0 8px 0 0' }} /> Drafting memorandum...</> : <><FileText size={20} /> Generate Memorandum</>}
        </button>

        {(report || loading || error) && (
          <div className="glass-card report-stage-card">
            <div className="section-heading compact">
              <div>
                <span className="section-step">Step 3</span>
                <h3><FileText size={18} /> Review and export</h3>
              </div>
              <span className="section-note">Structured memo with investment context and export controls</span>
            </div>
            {revenueWarning && <div className="signal-warning warning-amber">{revenueWarning}</div>}
            {error && <div className="error-message">{error}</div>}

            {loading && !report && (
              <div style={{ textAlign: 'center', color: '#38bdf8', padding: '1rem' }}>
                <div className="loader" style={{ margin: '0 auto 10px', borderColor: '#0284c7', borderTopColor: '#38bdf8' }} />
                <p style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: '1rem' }}>{loadingMessage}</p>
                <button 
                  onClick={onStopAnalysis} 
                  className="btn-secondary" 
                  style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid #ef4444', width: 'auto', padding: '4px 12px', fontSize: '0.8rem' }}
                >
                  🛑 Stop Analysis
                </button>
              </div>
            )}
            {report && (
              <div ref={reportRef}>
                <div className="report-shell">
                  <div className="quick-insights-grid report-summary-grid">
                    <div className="quick-insight-card tone-neutral">
                      <span className="quick-insight-label">Parcel size</span>
                      <strong>{area} acres</strong>
                    </div>
                    <div className={`quick-insight-card ${selectedGssDistance ? 'tone-good' : 'tone-muted'}`}>
                    <span className="quick-insight-label">Nearest GSS</span>
                    <strong>{selectedGssDistance ? `${selectedGssDistance} km` : 'Pending'}</strong>
                  </div>
                    <div className={`quick-insight-card ${revenueWarning ? 'tone-risk' : 'tone-good'}`}>
                      <span className="quick-insight-label">Constraint signal</span>
                      <strong>{revenueWarning ? 'Needs verification' : 'No active warning'}</strong>
                    </div>
                  </div>
                  <div className="report-toolbar">
                    <div>
                      <h3>Investment Memorandum</h3>
                      <span>Executive summary, evidence, and supporting analysis</span>
                    </div>
                    <div className="report-toolbar-actions">
                      <button onClick={onExpandReport} className="btn-secondary report-icon-btn" aria-label="Expand report">
                        <Maximize2 size={14} />
                      </button>
                      <button onClick={onDownloadPdf} className="btn-primary report-icon-btn report-icon-btn--primary" aria-label="Download PDF">
                        <Download size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="report-body">
                    <div className="markdown-body report-markdown">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!report && !loading && !error && (
              <div className="glass-card report-empty-state">
            <div className="section-heading compact">
              <div>
                <span className="section-step">Ready</span>
                <h3><FileText size={18} /> Report preview</h3>
              </div>
              <span className="section-note">Your report will appear here once it is generated</span>
            </div>
            <p className="empty-state-copy">
              {hasInputs
                ? `Inputs are ready. Generate a ${area}-acre decision memo with map context, risk signals, and export-ready output.`
                : 'Set a location or upload a parcel boundary, then generate the report.'}
            </p>
              <div className="empty-state-actions">
              <div className="empty-state-pill">Executive thesis</div>
              <div className="empty-state-pill">Risk-ranked sections</div>
              <div className="empty-state-pill">PDF export ready</div>
            </div>
          </div>
        )}

        <details className="advanced-options-details" style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
          <summary style={{ cursor: 'pointer', color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1rem', outline: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem', userSelect: 'none' }}>
            <Layers size={14} /> Advanced tools
          </summary>
          <div className="glass-card nested-card" style={{ borderTop: '4px solid #ef4444', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontWeight: 600, color: '#ef4444' }}>
              <Shield size={18} /> Private notes
            </div>
            <input type="text" className="input-field" placeholder="GSS Name" value={intelTargetGss} onChange={(e) => setIntelTargetGss(e.target.value)} />
            <textarea className="input-field" placeholder="Specific rules..." rows="2" value={intelText} onChange={(e) => setIntelText(e.target.value)} style={{ resize: 'vertical' }} />
            <button onClick={onSubmitIntel} disabled={isSubmittingIntel || !intelTargetGss || !intelText} className="btn-primary" style={{ background: '#ef4444', border: 'none' }}>
              Save note
            </button>
            {intelStatus === 'success' && <div style={{ color: '#10b981', fontSize: '0.8rem', textAlign: 'center' }}>Secured ✓</div>}
          </div>

          <div className="glass-card nested-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#38bdf8', fontWeight: 600 }}>
              <MessageSquarePlus size={18} /> Analyst feedback loop
            </div>
            <textarea
              className="input-field"
              placeholder="Add correction, missed constraint, or better ranking guidance for future runs."
              rows="3"
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              style={{ resize: 'vertical' }}
            />
            <button onClick={onSubmitFeedback} disabled={isSubmittingFeedback || !feedbackText.trim()} className="btn-secondary">
              {isSubmittingFeedback ? <><Loader size={14} className="spin-inline" /> Saving...</> : 'Save feedback'}
            </button>
            {feedbackSuccess && <div style={{ color: '#10b981', fontSize: '0.8rem' }}>Feedback captured for future runs.</div>}
          </div>
        </details>
      </div>
    </div>
  );
}
