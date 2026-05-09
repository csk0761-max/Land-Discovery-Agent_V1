import re

with open("frontend/src/LandDiscoveryAgent.jsx", "r") as f:
    content = f.read()

# Add ChevronDown to lucide imports
content = content.replace("import { ArrowLeft } from 'lucide-react';", "import { ArrowLeft, ChevronDown } from 'lucide-react';")

# Modify sidebar container and add floating toggle button
sidebar_pattern = r'<div className=\{`gss-sidebar \$\{isLeftMinimized \? \'minimized\' : \'\'\} \$\{isMobileLayout \? \'mobile-drawer\' : \'\'\} \$\{isMobileLayout && !isMobileLeftOpen \? \'drawer-collapsed\' : \'drawer-open\'\}`\} style=\{\{ width: isMobileLayout \? \'100%\' : \(isLeftMinimized \? \'50px\' : leftWidth \+ \'px\'\), minWidth: isMobileLayout \? \'100%\' : \(isLeftMinimized \? \'50px\' : \' unset\'\) \}\}>'
sidebar_replacement = """{isLeftMinimized && (
          <button type="button" className="floating-reopen-btn" onClick={() => setIsLeftMinimized(false)}>
            <Maximize2 size={16} /> Open Panel
          </button>
        )}
        <div className={`gss-sidebar ${isLeftMinimized ? 'minimized' : ''} ${isMobileLayout ? 'mobile-drawer' : ''} ${isMobileLayout && !isMobileLeftOpen ? 'drawer-collapsed' : 'drawer-open'}`} style={{ width: isMobileLayout ? '100%' : (isLeftMinimized ? '0px' : leftWidth + 'px'), minWidth: isMobileLayout ? '100%' : (isLeftMinimized ? '0px' : 'unset') }}>"""
content = re.sub(sidebar_pattern, sidebar_replacement, content)

# Remove the 'Site Parameters' minimized label since we use a floating button now
label_pattern = r'\{!isMobileLayout && isLeftMinimized && \(\s*<div className="minimized-sidebar-label" onClick=\{\(\) => setIsLeftMinimized\(false\)\}>\s*<Radar size=\{18\} /> <span>Site Parameters</span>\s*</div>\s*\)\}'
content = re.sub(label_pattern, '', content)

# Now for the big block:
# Replace the whole structure from `<div className="glass-card insight-strip-card">` down to `</div>` of `{plotInfo && ...}`
import sys
start_idx = content.find('<div className="glass-card insight-strip-card">')
if start_idx == -1:
    print("Could not find start of insight-strip-card")
    sys.exit(1)

# we need to find the end of `{plotInfo && ( ... )}` which is followed by `</div>` for sidebar-scrollable
# It's easier to find the end by looking for the `</div>` just before `{!isMobileLayout && isLeftMinimized &&`
end_idx = content.find('</div>', content.find(')}', content.find('{plotInfo &&'))) + 6

# Wait, let's use exact strings if possible.
