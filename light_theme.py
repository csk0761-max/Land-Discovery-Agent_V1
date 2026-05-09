import os
import re

css_files = [
    'frontend/src/LandDiscoveryAgent.css',
    'frontend/src/AutoSearchAgent.css',
    'frontend/src/GridMappingEngine.css',
    'frontend/src/LayerControlPanel.css',
]

color_map = {
    # Dark backgrounds -> Light backgrounds
    r'#0f172a': '#ffffff',
    r'#1e293b': '#f8fafc',
    r'#334155': '#e2e8f0',
    r'#475569': '#cbd5e1',
    r'#020617': '#f1f5f9',

    # Light texts -> Dark texts
    r'#cbd5e1': '#475569',
    r'#e2e8f0': '#334155',
    r'#f1f5f9': '#1e293b',
    r'#f8fafc': '#0f172a',

    # RGBA mappings
    r'rgba\(15,\s*23,\s*42,': 'rgba(255, 255, 255,',
    r'rgba\(30,\s*41,\s*59,': 'rgba(248, 250, 252,',
    r'rgba\(51,\s*65,\s*85,': 'rgba(226, 232, 240,',

    # Primary colors shifted darker for contrast
    r'#38bdf8': '#0284c7',   
    r'#7dd3fc': '#0369a1',   
    r'#bae6fd': '#075985',
    r'#e0f2fe': '#082f49',
    r'rgba\(56,\s*189,\s*248,': 'rgba(2, 132, 199,', 

    r'#93c5fd': '#2563eb',   
    r'rgba\(147,\s*197,\s*253,': 'rgba(37, 99, 235,',

    r'#94a3b8': '#64748b',   
}

def replace_colors(text):
    # Pass 1: Replace with placeholders to avoid circular replacements
    placeholders = {}
    for k, v in color_map.items():
        placeholder = f"__PLACEHOLDER_{abs(hash(k))}__"
        placeholders[placeholder] = v
        text = re.sub(k, placeholder, text, flags=re.IGNORECASE)
    
    # Pass 2: Substitute placeholders
    for placeholder, v in placeholders.items():
        text = text.replace(placeholder, v)
        
    return text

for file_path in css_files:
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read()
        
        new_content = replace_colors(content)
        
        with open(file_path, 'w') as f:
            f.write(new_content)
        print(f"Updated {file_path}")

