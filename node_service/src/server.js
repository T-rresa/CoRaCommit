// node_service/src/server.js
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();

const configController = require('./controllers/configController');
const commitController = require('./controllers/commitController');
const statsController = require('./controllers/statsController');
// const feedbackController = require('./controllers/feedbackController'); // Lazy load this

const app = express();
const port = process.env.PORT || 3001;

app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));

// Health Check
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', version: '2.0.0', service: 'node-orchestrator' });
});

// Config Routes
app.get('/api/config/models', configController.getModels);
app.post('/api/config/models/init-scores', configController.initModelScores);
app.post('/api/config/models/add', configController.addNewModel);
app.get('/api/config/templates', configController.getTemplates);
app.get('/api/config/languages', configController.getLanguages);

// Core Business Routes
app.post('/api/commit-suggestion', commitController.suggestCommit);
app.post('/api/similarity-search', commitController.similaritySearch);
app.post('/api/examples/model-scores', commitController.getExampleModelScores);

// Lazy load feedbackController to avoid crashing if Redis is not available during startup
// Redis is only required for feedback queue and rankings
app.post('/api/feedback/commit', (req, res, next) => {
    try {
        const feedbackController = require('./controllers/feedbackController');
        feedbackController.saveFeedback(req, res);
    } catch (error) {
        console.error("Failed to load feedbackController (likely Redis issue):", error.message);
        res.status(503).json({ error: "Service Unavailable: Feedback system requires Redis" });
    }
});

app.get('/api/models/ranking', (req, res, next) => {
    try {
        const feedbackController = require('./controllers/feedbackController');
        feedbackController.getModelRankings(req, res);
    } catch (error) {
        // Fallback or error
        console.error("Failed to load feedbackController for rankings:", error.message);
        res.status(503).json({ error: "Service Unavailable: Ranking system requires Redis" });
    }
});

app.get('/api/stats/model-usage', statsController.getModelUsageStats);

// Start Server
app.listen(port, () => {
    console.log(`Node Orchestrator running on port ${port}`);
    console.log(`Retrieval Backend: ${process.env.RETRIEVAL_BACKEND_URL || process.env.BACKEND_URL || "http://localhost:8000"}`);
    console.log(`Evaluation Backend: ${process.env.EVALUATION_BACKEND_URL || process.env.BACKEND_URL || "http://localhost:8001"}`);
});
