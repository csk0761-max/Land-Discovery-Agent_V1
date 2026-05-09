import React from 'react';
import { Link } from 'react-router-dom';
import Logo from './Logo';
import { Map, Bot, Zap, Building, ArrowRight, Activity, Radar, MapPinned, FileCheck } from 'lucide-react';
import './MissionControl.css';

export default function MissionControl() {
    const agents = [
        {
            id: 'land-discovery',
            title: 'Land Discovery Agent',
            description: 'Real-time GIS intelligence and AI feasibility assessment for renewable energy using live Earth Engine data.',
            icon: <Map className="agent-icon" size={32} />,
            status: 'active',
            tag: 'Parcel due diligence',
            readiness: 'Live workflow',
            link: '/land-discovery'
        }
    ];

    const stats = [
        { label: 'Active agents', value: '1', icon: <Activity size={18} /> },
        { label: 'Planning surfaces', value: 'GIS + AI', icon: <Radar size={18} /> },
        { label: 'Primary use case', value: 'Renewables siting', icon: <MapPinned size={18} /> },
    ];

    return (
        <div className="mission-control-container">
            <header className="mc-header">
                <div className="mc-hero-card">
                    <div className="mc-brand">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                            <Logo width="160px" />
                            <button 
                                onClick={() => {
                                    import('./supabaseClient').then(({ supabase }) => supabase.auth.signOut());
                                }}
                                style={{
                                    background: 'rgba(255, 255, 255, 0.1)',
                                    border: '1px solid rgba(255, 255, 255, 0.2)',
                                    color: 'white',
                                    padding: '8px 16px',
                                    borderRadius: '8px',
                                    cursor: 'pointer',
                                    fontSize: '13px',
                                    fontWeight: '600',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}
                            >
                                <Zap size={14} /> Sign Out
                            </button>
                        </div>
                        <span className="mc-kicker">Start here to launch land analysis workflows</span>
                    </div>
                    <div className="mc-hero-copy">
                        <h1 className="mc-title">Land Intelligence Hub</h1>
                        <p className="mc-subtitle">Choose a workflow, add a location, and turn geospatial inputs into a decision-ready report.</p>
                    </div>
                    <div className="mc-stats-grid">
                        {stats.map((stat) => (
                            <div key={stat.label} className="mc-stat-card">
                                <div className="mc-stat-icon">{stat.icon}</div>
                                <div>
                                    <div className="mc-stat-value">{stat.value}</div>
                                    <div className="mc-stat-label">{stat.label}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </header>

            <div className="agents-grid">
                {agents.map((agent) => (
                    <div key={agent.id} className={`agent-card ${agent.status}`}>
                        <div className="agent-card-header">
                            <div className="icon-wrapper">
                                {agent.icon}
                            </div>
                            {agent.status === 'coming-soon' && (
                                <span className="badge-coming-soon">Coming Soon</span>
                            )}
                            {agent.status === 'active' && (
                                <span className="badge-active">
                                    <div className="pulsating-dot" />
                                    Online
                                </span>
                            )}
                        </div>

                        <div className="agent-card-meta">
                            <span className="agent-tag">{agent.tag}</span>
                            <span className="agent-readiness">{agent.readiness}</span>
                        </div>

                        <h3 className="agent-card-title">{agent.title}</h3>
                        <p className="agent-card-desc">{agent.description}</p>

                        <div className="agent-card-footer">
                            {agent.status === 'active' ? (
                                <Link to={agent.link} className="agent-btn active-btn">
                                    Open Workflow <ArrowRight size={16} />
                                </Link>
                            ) : (
                                <button className="agent-btn disabled-btn" disabled>
                                    In Development
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
