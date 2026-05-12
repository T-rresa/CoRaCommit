const pool = require('./src/config/db');
const { AVAILABLE_MODELS } = require('./src/config/settings');

const INITIAL_SCORE = 0.6;

async function initModelScoresTable() {
    console.log(`Starting initialization for ${AVAILABLE_MODELS.length} models in model_scores...`);
    
    try {
        const connection = await pool.getConnection();
        
        try {
            await connection.beginTransaction();

            for (const model of AVAILABLE_MODELS) {
                // Check if model exists
                const [rows] = await connection.query('SELECT * FROM model_scores WHERE model_name = ?', [model.name]);
                
                if (rows.length === 0) {
                    console.log(`Inserting initial score for ${model.name}`);
                    await connection.query(
                        'INSERT INTO model_scores (model_name, score, count) VALUES (?, ?, 0)',
                        [model.name, INITIAL_SCORE]
                    );
                } else {
                    console.log(`Model ${model.name} already exists, skipping.`);
                }
            }

            await connection.commit();
            console.log('✅ Initialization of model_scores completed successfully.');
        } catch (err) {
            await connection.rollback();
            throw err;
        } finally {
            connection.release();
        }
    } catch (error) {
        console.error('❌ Initialization failed:', error);
    } finally {
        process.exit();
    }
}

// Run the script
initModelScoresTable();
