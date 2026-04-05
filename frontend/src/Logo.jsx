import React from 'react';

export default function Logo({ width = "100%", height = "auto", className = "" }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 240" width={width} height={height} className={className}>
            <g transform="translate(10, 10) scale(1.1)">
                {/* Top Left Blue */}
                <path d="M 95 95 L 95 0 A 95 95 0 0 0 0 95 Z" fill="#006cb5" />
                {/* Top Right Yellow */}
                <path d="M 105 95 L 200 95 A 95 95 0 0 0 105 0 Z" fill="#ffd100" />
                {/* Bottom Left Green */}
                <path d="M 95 105 L 0 105 A 95 95 0 0 0 95 200 Z" fill="#399566" />

                {/* Map Pin at Bottom Right */}
                <g transform="translate(105, 105) scale(0.95)">
                    {/* Jagged map path under pin */}
                    <path d="M 5 50 L 35 60 L 65 45 L 90 60 L 80 95 L 45 105 L 15 85 Z" fill="none" stroke="#594a42" strokeWidth="6" strokeLinejoin="round" />
                    {/* Pin */}
                    <path d="M 50 10 C 30 10 15 25 15 45 C 15 65 50 100 50 100 C 50 100 85 65 85 45 C 85 25 70 10 50 10 Z" fill="#594a42" />
                    <circle cx="50" cy="45" r="15" fill="#ffffff" />
                </g>
            </g>

            {/* Texts */}
            <text x="250" y="140" fontFamily="'Inter', sans-serif" fontWeight="900" fontSize="110" fill="#113661" letterSpacing="1">AUXILIUM</text>
            <text x="260" y="200" fontFamily="'Inter', sans-serif" fontWeight="400" fontSize="38" fill="#727272">by ZVERVE</text>
        </svg>
    );
}
