// Builds the deployable site into Frontend/dist.
//
//   API_BASE=https://your-api.onrender.com npm run build
//
// Pages move to the top level, so the live addresses are clean
// (/login.html, not /HTML's/login.html). Nothing else is rewritten: a page at
// the top level still finds "../Assets/..." and "../Javascript's/..." because
// browsers treat ".." at the top of a site as the top itself.
// The build also points the app at the live API and adds a Content-Security-Policy.
const fs = require('fs');
const path = require('path');

const root = __dirname;
const dist = path.join(root, 'dist');
const apiBase = (process.env.API_BASE || '').trim().replace(/\/+$/, '');

if (apiBase && !/^https:\/\/[^\s/]+$/.test(apiBase)) {
    console.error(`API_BASE must look like https://your-api.onrender.com (got "${apiBase}")`);
    process.exit(1);
}

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(dist);

// Pages, manifest and service worker go to the top level.
fs.cpSync(path.join(root, "HTML's"), dist, { recursive: true });
// Shared folders keep their names so no page needs editing.
for (const dir of ['Assets', "Javascript's", 'vendor']) {
    fs.cpSync(path.join(root, dir), path.join(dist, dir), { recursive: true });
}
fs.mkdirSync(path.join(dist, 'css'));
fs.copyFileSync(path.join(root, 'css', 'app.css'), path.join(dist, 'css', 'app.css'));

// Point the app at the live API.
const apiFile = path.join(dist, "Javascript's", 'api.js');
const placeholder = "'https://YOUR-BACKEND-URL.onrender.com'";
let apiJs = fs.readFileSync(apiFile, 'utf8');
if (!apiJs.includes(placeholder)) {
    console.error('Could not find the PRODUCTION_API_BASE placeholder in api.js');
    process.exit(1);
}
if (apiBase) {
    fs.writeFileSync(apiFile, apiJs.replace(placeholder, `'${apiBase}'`));
} else {
    console.warn('WARNING: API_BASE is not set. The built site will not reach any backend.');
}

// Content-Security-Policy: the pages may only load their own files and talk to our API.
// 'unsafe-inline' stays because the pages use small inline scripts and handlers.
const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self'${apiBase ? ' ' + apiBase : ''}`,
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
].join('; ');
const cspTag = `<meta http-equiv="Content-Security-Policy" content="${csp}">`;

let pages = 0;
for (const file of fs.readdirSync(dist)) {
    if (!file.endsWith('.html')) continue;
    const full = path.join(dist, file);
    const html = fs.readFileSync(full, 'utf8');
    const withCsp = html.replace(/<meta charset="utf-8"\s*\/?>/i, m => `${m}\n${cspTag}`);
    if (withCsp === html) {
        console.error(`No <meta charset> found in ${file}; cannot add the security policy.`);
        process.exit(1);
    }
    fs.writeFileSync(full, withCsp);
    pages++;
}

// The site's front door: logged-in visitors go to the dashboard, everyone else to login.
fs.writeFileSync(path.join(dist, 'index.html'), `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
${cspTag}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#66547b">
<title>Budget Buddy</title>
<link rel="manifest" href="manifest.json">
<link rel="icon" type="image/png" sizes="192x192" href="Assets/icons/icon-192.png">
<style>body{margin:0;background:#fef8fb}</style>
<script>
    var loggedIn = false;
    try { loggedIn = !!localStorage.getItem('bb_token'); } catch (e) {}
    location.replace(loggedIn ? 'dashboard.html' : 'login.html');
</script>
</head><body><noscript><a href="login.html">Open Budget Buddy</a></noscript></body></html>
`);

console.log(`Built ${pages} pages into dist/ (API: ${apiBase || 'not set'})`);
