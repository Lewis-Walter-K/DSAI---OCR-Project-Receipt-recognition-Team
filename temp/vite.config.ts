import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'url'
import path from 'path'
import fs from 'fs'
import { execFile } from 'child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(__dirname, '..')
const PYTHON_EXEC = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
const MAIN_PY = path.join(PROJECT_ROOT, 'Candidate_classification', 'main.py')
const UPLOAD_DIR = path.join(PROJECT_ROOT, 'Candidate_classification', 'input')

function pythonApiPlugin() {
  return {
    name: 'python-api-plugin',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url === '/api/process-receipt' && req.method === 'POST') {
          try {
            const chunks = [];
            for await (const chunk of req) {
              chunks.push(chunk);
            }
            const buffer = Buffer.concat(chunks);

            if (!fs.existsSync(UPLOAD_DIR)) {
              fs.mkdirSync(UPLOAD_DIR, { recursive: true });
            }
            
            const imagePath = path.join(UPLOAD_DIR, 'test1.jpg');
            fs.writeFileSync(imagePath, buffer);

            const pythonCmd = fs.existsSync(PYTHON_EXEC) ? PYTHON_EXEC : 'python';
            
            execFile(pythonCmd, [MAIN_PY, imagePath], { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
              const startMarker = "===RESULT_JSON_START===";
              const endMarker = "===RESULT_JSON_END===";
              const startIdx = stdout.indexOf(startMarker);
              const endIdx = stdout.indexOf(endMarker);
              
              if (startIdx !== -1 && endIdx !== -1) {
                const jsonStr = stdout.substring(startIdx + startMarker.length, endIdx).trim();
                res.setHeader('Content-Type', 'application/json');
                res.end(jsonStr);
              } else {
                console.error("Python stderr:", stderr);
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to parse Python output", stdout, stderr, exception: error?.message }));
              }
            });
          } catch (err) {
            console.error(err);
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.message }));
          }
        } else if (req.url === '/api/feedback' && req.method === 'POST') {
          try {
            const chunks = [];
            for await (const chunk of req) {
              chunks.push(chunk);
            }
            const body = JSON.parse(Buffer.concat(chunks).toString());

            const pythonCmd = fs.existsSync(PYTHON_EXEC) ? PYTHON_EXEC : 'python';
            execFile(pythonCmd, [MAIN_PY, '--feedback', '--candidates', JSON.stringify(body.candidates), '--correct_value', body.correct_value.toString()], { encoding: 'utf8' }, (error, stdout, stderr) => {
              const startMarker = "===RESULT_JSON_START===";
              const endMarker = "===RESULT_JSON_END===";
              const startIdx = stdout.indexOf(startMarker);
              const endIdx = stdout.indexOf(endMarker);
              
              if (startIdx !== -1 && endIdx !== -1) {
                const jsonStr = stdout.substring(startIdx + startMarker.length, endIdx).trim();
                res.setHeader('Content-Type', 'application/json');
                res.end(jsonStr);
              } else {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "Failed to parse Python output", stdout, stderr }));
              }
            });
          } catch (err) {
            console.error(err);
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.message }));
          }
        } else {
          next();
        }
      });
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), pythonApiPlugin()],
})
