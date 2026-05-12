const axios = require('axios');
const { AVAILABLE_MODELS } = require('./src/config/settings');

// Configuration
const API_URL = 'http://localhost:3001/api/config/models/init-scores';
const INITIAL_SCORE = 0.6;

async function initAllModels() {
    console.log(`Starting initialization for ${AVAILABLE_MODELS.length} models...`);
    
    for (const model of AVAILABLE_MODELS) {
        console.log(`Initializing scores for model: ${model.name}`);
        try {
            const response = await axios.post(API_URL, {
                model_name: model.name,
                initial_score: INITIAL_SCORE
            });
            
            if (response.data.success) {
                console.log(`✅ Success: ${model.name} - Inserted ${response.data.details.insertedRows} rows`);
            } else {
                console.warn(`⚠️ Warning: ${model.name} - ${response.data.message}`);
            }
        } catch (error) {
            if (error.response) {
                console.error(`❌ Error: ${model.name} - Status ${error.response.status}: ${JSON.stringify(error.response.data)}`);
            } else {
                console.error(`❌ Error: ${model.name} - Connection failed: ${error.message}`);
            }
        }
    }
    console.log('Initialization process completed.');
}

// Run the script
initAllModels();
