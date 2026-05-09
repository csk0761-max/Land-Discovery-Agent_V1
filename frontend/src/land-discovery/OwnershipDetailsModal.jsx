import React from 'react';
import { X } from 'lucide-react';

export default function OwnershipDetailsModal({ open, ownershipDetails, onClose }) {
  if (!open || !ownershipDetails) return null;

  return (
    <div className="khasra-modal-overlay" onClick={onClose}>
      <div className="khasra-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="khasra-modal-header">
          <h3>Verified Ownership Records ({ownershipDetails.total_khasras_found || 0})</h3>
          <button className="khasra-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="khasra-modal-body">
          <table className="khasra-table">
            <thead>
              <tr>
                <th>Survey No.</th>
                <th>Khasra/Base No.</th>
                <th>Owner Name</th>
                <th>Area (Acres)</th>
                <th>Land Type / Details</th>
              </tr>
            </thead>
            <tbody>
              {(ownershipDetails.khasra_records || []).map((record, index) => (
                <tr key={`${record.survey_no || record.khasra_no || 'survey'}-${index}`}>
                  <td>{record.survey_no || 'N/A'}</td>
                  <td>{record.khasra_no || 'N/A'}</td>
                  <td style={{ fontWeight: '500', color: '#38bdf8' }}>{record.owner || 'Unavailable'}</td>
                  <td>{record.area_acres ?? 'N/A'}</td>
                  <td style={{ fontSize: '0.85rem' }}>{record.owner_details || record.land_type || 'Unavailable'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
