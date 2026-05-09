import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { supabase } from './supabaseClient';
import MissionControl from './MissionControl';
import LandDiscoveryAgent from './LandDiscoveryAgent';
import LoginPage from './LoginPage';

const ProtectedRoute = ({ children }) => {
    const [session, setSession] = useState(undefined);

    useEffect(() => {
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session);
        });

        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            setSession(session);
        });

        return () => subscription.unsubscribe();
    }, []);

    if (session === undefined) {
        return (
            <div style={{
                minHeight: '100vh',
                display: 'grid',
                placeItems: 'center',
                background: 'linear-gradient(135deg, #0f172a 0%, #111827 100%)',
                color: '#e2e8f0',
                fontFamily: 'system-ui, sans-serif',
            }}>
                <div style={{ textAlign: 'center' }}>
                    <div className="loader" style={{ margin: '0 auto 16px' }} />
                    <div>Loading your workspace...</div>
                </div>
            </div>
        );
    }
    if (!session) return <Navigate to="/login" replace />;

    return children;
};

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route 
                    path="/" 
                    element={
                        <ProtectedRoute>
                            <LandDiscoveryAgent />
                        </ProtectedRoute>
                    } 
                />
                <Route
                    path="/hub"
                    element={
                        <ProtectedRoute>
                            <MissionControl />
                        </ProtectedRoute>
                    }
                />
                {/* Redirect any old hub links to the main agent */}
                <Route path="/land-discovery" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
