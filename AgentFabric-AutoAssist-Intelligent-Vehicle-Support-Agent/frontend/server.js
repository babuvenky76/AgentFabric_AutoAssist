/**
 * Simple HTTP Server for AutoAssist Frontend
 * Serves static files on port 3000
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const FRONTEND_DIR = path.join(__dirname);

const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon'
};

const server = http.createServer((req, res) => {
    // Default to index.html
    let filePath = path.join(FRONTEND_DIR, req.url === '/' ? 'index.html' : req.url);
    
    // Security: prevent directory traversal
    if (!filePath.startsWith(FRONTEND_DIR)) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
    }
    
    // Try to read the file
    fs.readFile(filePath, (err, content) => {
        if (err) {
            // File not found, try index.html for SPA routing
            if (err.code === 'ENOENT') {
                fs.readFile(path.join(FRONTEND_DIR, 'index.html'), (err2, content2) => {
                    if (err2) {
                        res.writeHead(404, { 'Content-Type': 'text/plain' });
                        res.end('404 Not Found');
                    } else {
                        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
                        res.end(content2);
                    }
                });
            } else {
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Internal Server Error');
            }
        } else {
            // Determine content type
            const ext = path.extname(filePath).toLowerCase();
            const contentType = MIME_TYPES[ext] || 'application/octet-stream';
            
            // Set cache headers for static assets
            const headers = {
                'Content-Type': contentType,
                'Access-Control-Allow-Origin': '*'
            };
            
            if (ext !== '.html') {
                headers['Cache-Control'] = 'public, max-age=31536000';
            } else {
                headers['Cache-Control'] = 'public, max-age=3600';
            }
            
            res.writeHead(200, headers);
            res.end(content);
        }
    });
});

server.listen(PORT, () => {
    console.log(`AutoAssist Frontend server running on http://localhost:${PORT}`);
    console.log(`Serving files from: ${FRONTEND_DIR}`);
});
