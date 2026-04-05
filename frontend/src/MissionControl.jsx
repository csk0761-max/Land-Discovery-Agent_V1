import React from 'react';
import { Link } from 'react-router-dom';
import Logo from './Logo';
import { Map, Bot, Zap, Building, ArrowRight } from 'lucide-react';
import './MissionControl.css';

export default function MissionControl() {
    const agents = [
        {
            id: 'land-discovery',
            title: 'Land Discovery Agent',
            description: 'Real-time GIS intelligence and AI feasibility assessment for renewable energy using live Earth Engine data.',
            icon: <Map className="agent-icon" size={32} />,
            status: 'active',
            link: '/land-discovery'
        },
        {
            id: 'financial-analysis',
            title: 'Financial Analysis Agent',
            description: 'Deep dive ROI calculations, carbon credit forecasting, and capEx estimations.',
            icon: <Zap className="agent-icon" size={32} />,
            status: 'coming-soon',
            link: '#'
        },
        {
            id: 'regulatory-compliance',
            title: 'Regulatory & Policy Agent',
            description: 'Automated compliance checking against local, state, and federal renewable policies.',
            icon: <Building className="agent-icon" size={32} />,
            status: 'coming-soon',
            link: '#'
        },
        {
            id: 'custom-builder',
            title: 'Agent Builder',
            description: 'Construct your own specialized agents tailored for your specific organizational workflows.',
            icon: <Bot className="agent-icon" size={32} />,
            status: 'coming-soon',
            link: '#'
        }
    ];

    return (
        <div className="mission-control-container">
            <header className="mc-header">
                <Logo width="450px" />
                <h1 className="mc-title">Mission Control Hub</h1>
                <p className="mc-subtitle">Select an AI Agent to deploy and analyze.</p>
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
                                <span className="badge-active">Online</span>
                            )}
                        </div>

                        <h3 className="agent-card-title">{agent.title}</h3>
                        <p className="agent-card-desc">{agent.description}</p>

                        <div className="agent-card-footer">
                            {agent.status === 'active' ? (
                                <Link to={agent.link} className="agent-btn active-btn">
                                    Launch Agent <ArrowRight size={16} />
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
