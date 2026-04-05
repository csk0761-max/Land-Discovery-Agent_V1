const http = require('http');
const req = http.request('http://localhost:8000/auto-search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
}, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const d = JSON.parse(data);
    const c = d.candidates[0];
    console.log("c.lat type:", typeof c.lat, "value:", c.lat);
    console.log("c.lon type:", typeof c.lon, "value:", c.lon);
  });
});
req.write(JSON.stringify({
  state: "Goa",
  district: "North Goa",
  project_type: "solar",
  capacity_mw: 100,
  area_acres: 500
}));
req.end();
