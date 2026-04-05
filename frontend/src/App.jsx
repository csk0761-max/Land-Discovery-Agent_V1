import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MissionControl from './MissionControl';
import LandDiscoveryAgent from './LandDiscoveryAgent';

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<MissionControl />} />
                <Route path="/land-discovery" element={<LandDiscoveryAgent />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
