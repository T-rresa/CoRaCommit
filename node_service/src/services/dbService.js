const pool = require('../config/db');
const logger = require('./loggerService');
const { redisClient } = require('../config/redis');
const {
    MODEL_SCORE_UPDATE_STRATEGY,
    MODEL_SCORE_EMA_ALPHA
} = require('../config/settings');

class DbService {
    getModelScoreUpdateConfig() {
        const strategy = MODEL_SCORE_UPDATE_STRATEGY;
        if (!['global_mean', 'global_ema'].includes(strategy)) {
            throw new Error(`Unsupported MODEL_SCORE_UPDATE_STRATEGY: ${strategy}`);
        }

        return {
            strategy,
            emaAlpha: MODEL_SCORE_EMA_ALPHA
        };
    }

    computeUpdatedGlobalScore({ strategy, currentScore, currentCount, newScore }) {
        if (strategy === 'global_mean') {
            return ((currentScore * currentCount) + newScore) / (currentCount + 1);
        }

        if (strategy === 'global_ema') {
            const alpha = MODEL_SCORE_EMA_ALPHA;
            return (alpha * newScore) + ((1 - alpha) * currentScore);
        }

        throw new Error(`Unsupported global score update strategy: ${strategy}`);
    }

    async getConnection() {
        return await pool.getConnection();
    }

    async saveCommitFeedback(data) {
        const { user_id, models_requested, candidates, selected_model, final_message, is_edited, timestamp, example_ids, diff } = data;

        const query = `
            INSERT INTO commit_logs 
            (user_id, models_requested, candidates, selected_model, final_message, is_edited, created_at, example_ids, diff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;

        const values = [
            user_id,
            JSON.stringify(models_requested),
            JSON.stringify(candidates),
            selected_model,
            final_message,
            is_edited,
            new Date(timestamp),
            JSON.stringify(example_ids || []),
            diff || ""
        ];

        try {
            const [result] = await pool.execute(query, values);
            logger.info('DB', `Saved feedback`, { insertId: result.insertId });
            return result;
        } catch (error) {
            logger.error('DB', `Failed to save feedback`, { error: error.message });
            throw error;
        }
    }

    async logModelEvaluation(session_id, modelName, metrics, connection = pool) {
        const query = `
            INSERT INTO evaluation_logs 
            (session_id, model_name, semantic_score, lexical_score, sim_score, user_preference, single_score, compare_score, final_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        `;

        const values = [
            session_id,
            modelName,
            metrics.semantic_score,
            metrics.lexical_score,
            metrics.sim_score,
            metrics.user_preference,
            metrics.single_score,
            metrics.compare_score,
            metrics.final_score
        ];

        try {
            const [result] = await connection.execute(query, values);
            logger.info('DB', `Saved evaluation log for ${modelName}`, { sessionId: session_id });
            return result;
        } catch (error) {
            logger.error('DB', `Failed to save evaluation log`, { error: error.message });
            // Don't throw here to avoid stopping the worker entirely for one failed log
            console.error(error);
        }
    }

    async logModelEvaluationsBatch(session_id, evaluatedCandidates, connection = pool) {
        if (!evaluatedCandidates || evaluatedCandidates.length === 0) return;

        const query = `
            INSERT INTO evaluation_logs 
            (session_id, model_name, semantic_score, lexical_score, sim_score, user_preference, single_score, compare_score, final_score)
            VALUES ?
        `;

        const values = evaluatedCandidates.map(candidate => [
            session_id,
            candidate.model,
            candidate.metrics.semantic_score,
            candidate.metrics.lexical_score,
            candidate.metrics.sim_score,
            candidate.metrics.user_preference,
            candidate.metrics.single_score,
            candidate.metrics.compare_score,
            candidate.metrics.final_score
        ]);

        try {
            const [result] = await connection.query(query, [values]);
            logger.info('DB', `Batch saved evaluation logs`, { sessionId: session_id, count: values.length });
            return result;
        } catch (error) {
            logger.error('DB', `Failed to batch save evaluation logs`, { error: error.message });
            throw error;
        }
    }

    async updateModelScore(modelName, newScore, connection = pool) {
        const { strategy } = this.getModelScoreUpdateConfig();
        // First, check if the model exists
        const selectQuery = `SELECT * FROM model_scores WHERE model_name = ? FOR UPDATE`;
        
        try {
            const [rows] = await connection.execute(selectQuery, [modelName]);
            let finalAvgScore = newScore;
            
            if (rows.length === 0) {
                // Insert new model
                const insertQuery = `INSERT INTO model_scores (model_name, score, count) VALUES (?, ?, 1)`;
                await connection.execute(insertQuery, [modelName, newScore]);
            } else {
                const currentAvg = parseFloat(rows[0].score);
                const currentCount = rows[0].count || 0;

                finalAvgScore = this.computeUpdatedGlobalScore({
                    strategy,
                    currentScore: currentAvg,
                    currentCount,
                    newScore
                });

                const updateQuery = `UPDATE model_scores SET score = ?, count = ?, last_updated = NOW() WHERE model_name = ?`;
                await connection.execute(updateQuery, [finalAvgScore, currentCount + 1, modelName]);
            }
            
            // Cache the updated score in Redis for quick access
            await redisClient.set(`model_score:${modelName}`, finalAvgScore);
            // Optionally, update a sorted set for ranking models
            await redisClient.zadd('model_rankings', finalAvgScore, modelName);

            logger.info('DB', `Updated score for model ${modelName}`, { strategy });
        } catch (error) {
            logger.error('DB', `Failed to update model score`, { error: error.message });
             console.error(error);
        }
    }

    async updateModelScoresBatch(evaluatedCandidates, connection = pool) {
        const { strategy } = this.getModelScoreUpdateConfig();

        try {
            for (const candidate of evaluatedCandidates) {
                const modelName = candidate.model;
                const newScore = candidate.metrics.final_score;

                // Lock the row
                const selectQuery = `SELECT * FROM model_scores WHERE model_name = ? FOR UPDATE`;
                const [rows] = await connection.execute(selectQuery, [modelName]);
                
                let finalAvgScore = newScore;

                if (rows.length === 0) {
                    const insertQuery = `INSERT INTO model_scores (model_name, score, count) VALUES (?, ?, 1)`;
                    await connection.execute(insertQuery, [modelName, newScore]);
                } else {
                    const currentAvg = parseFloat(rows[0].score);
                    const currentCount = rows[0].count || 0;
                    finalAvgScore = this.computeUpdatedGlobalScore({
                        strategy,
                        currentScore: currentAvg,
                        currentCount,
                        newScore
                    });
                    const updateQuery = `UPDATE model_scores SET score = ?, count = ?, last_updated = NOW() WHERE model_name = ?`;
                    await connection.execute(updateQuery, [finalAvgScore, currentCount + 1, modelName]);
                }

                // Update Redis (outside transaction or after commit is safer, but here is fine for cache)
                await redisClient.set(`model_score:${modelName}`, finalAvgScore);
                await redisClient.zadd('model_rankings', finalAvgScore, modelName);
            }
            logger.info('DB', `Batch updated model scores`, { count: evaluatedCandidates.length, strategy });
        } catch (error) {
            logger.error('DB', `Failed to batch update model scores`, { error: error.message });
            throw error;
        }
    }

    async getModelRankingsFromDB() {
        const query = `
            SELECT model_name as model, score 
            FROM model_scores 
            ORDER BY score DESC 
            LIMIT 10
        `;
        try {
            const [rows] = await pool.execute(query);
            return rows;
        } catch (error) {
            logger.error('DB', `Failed to get model rankings from DB`, { error: error.message });
            throw error;
        }
    }

    async updateExampleModelScore(exampleIds, modelName, singleScore, connection = pool) {
        // formula: score = 0.9 * score + 0.1 * single_score
        const ALPHA = 0.1;
        const DECAY = 0.9;
        
        if (!exampleIds || exampleIds.length === 0) return;
        
        try {
            // 1. Get current scores for these examples and this model
            const placeholders = exampleIds.map(() => '?').join(',');
            const selectQuery = `
                SELECT example_id, score 
                FROM example_model_scores 
                WHERE model_name = ? AND example_id IN (${placeholders})
                FOR UPDATE
            `;
            
            const [rows] = await connection.execute(selectQuery, [modelName, ...exampleIds]);
            
            const currentScores = {};
            rows.forEach(row => {
                currentScores[row.example_id] = row.score;
            });
            
            // 2. Prepare updates
            const updates = [];
            for (const id of exampleIds) {
                let newScore = singleScore;
                if (currentScores[id] !== undefined && currentScores[id] !== null) {
                    newScore = (DECAY * currentScores[id]) + (ALPHA * singleScore);
                }
                updates.push([id, modelName, newScore]);
            }
            
            // 3. Batch Insert/Update
            const updateQuery = `
                INSERT INTO example_model_scores (example_id, model_name, score) 
                VALUES ? 
                ON DUPLICATE KEY UPDATE score = VALUES(score), updated_at = NOW()
            `;
            
            await connection.query(updateQuery, [updates]);
            
            logger.info('DB', `Updated example scores for model ${modelName}`, { 
                count: updates.length
            });
            
        } catch (error) {
            logger.error('DB', `Failed to update example scores`, { error: error.message });
            console.error(error);
            throw error;
        }
    }

    async updateExampleModelScoresBatch(exampleIds, evaluatedCandidates, connection = pool) {
        if (!exampleIds || exampleIds.length === 0) return;
        if (!evaluatedCandidates || evaluatedCandidates.length === 0) return;

        const ALPHA = 0.1;
        const DECAY = 0.9;

        try {
            const allUpdates = [];

            for (const candidate of evaluatedCandidates) {
                const modelName = candidate.model;
                const singleScore = candidate.metrics.single_score;

                // 1. Get current scores
                const placeholders = exampleIds.map(() => '?').join(',');
                const selectQuery = `
                    SELECT example_id, score 
                    FROM example_model_scores 
                    WHERE model_name = ? AND example_id IN (${placeholders})
                    FOR UPDATE
                `;
                const [rows] = await connection.execute(selectQuery, [modelName, ...exampleIds]);
                
                const currentScores = {};
                rows.forEach(row => {
                    currentScores[row.example_id] = row.score;
                });

                // 2. Calculate new scores
                for (const id of exampleIds) {
                    let newScore = singleScore;
                    if (currentScores[id] !== undefined && currentScores[id] !== null) {
                        newScore = (DECAY * currentScores[id]) + (ALPHA * singleScore);
                    }
                    allUpdates.push([id, modelName, newScore]);
                }
            }

            // 3. Batch Execute
            if (allUpdates.length > 0) {
                const updateQuery = `
                    INSERT INTO example_model_scores (example_id, model_name, score) 
                    VALUES ? 
                    ON DUPLICATE KEY UPDATE score = VALUES(score), updated_at = NOW()
                `;
                await connection.query(updateQuery, [allUpdates]);
                logger.info('DB', `Batch updated example scores`, { totalUpdates: allUpdates.length });
            }

        } catch (error) {
            logger.error('DB', `Failed to batch update example scores`, { error: error.message });
            throw error;
        }
    }

    async getExampleModelScores(exampleIds) {
        if (!exampleIds || exampleIds.length === 0) return [];

        const placeholders = exampleIds.map(() => '?').join(',');
        const query = `
            SELECT example_id, model_name, score
            FROM example_model_scores
            WHERE example_id IN (${placeholders})
        `;

        try {
            const [rows] = await pool.execute(query, exampleIds);
            return rows.map(row => ({
                exampleId: row.example_id,
                model: row.model_name,
                score: parseFloat(row.score)
            }));
        } catch (error) {
            logger.error('DB', `Failed to get example model scores`, { error: error.message });
            return [];
        }
    }

    async getRecommendedModel(exampleScores) {
        // exampleScores: Array of { id: example_id, similarity: score }
        // Calculate weighted score for each model
        // Weighted Score = Sum(Example_Model_Score * Similarity) / Sum(Similarity)
        
        if (!exampleScores || exampleScores.length === 0) return null;

        const exampleIds = exampleScores.map(e => e.id);
        const placeholders = exampleIds.map(() => '?').join(',');
        
        const query = `
            SELECT model_name, example_id, score 
            FROM example_model_scores 
            WHERE example_id IN (${placeholders})
        `;
        
        try {
            const [rows] = await pool.execute(query, exampleIds);
            
            // Map: model_name -> total_weighted_score
            const modelScores = {};
            const totalSimilarity = exampleScores.reduce((sum, e) => sum + e.similarity, 0);
            
            // Create a lookup for similarity: example_id -> similarity
            const similarityMap = {};
            exampleScores.forEach(e => similarityMap[e.id] = e.similarity);
            
            rows.forEach(row => {
                const model = row.model_name;
                const score = row.score;
                const similarity = similarityMap[row.example_id] || 0;
                
                if (!modelScores[model]) {
                    modelScores[model] = 0;
                }
                
                // Add weighted score
                modelScores[model] += score * similarity;
            });
            
            // Normalize scores and find the best one
            let bestModel = null;
            let maxScore = -1;
            
            const result = Object.keys(modelScores).map(model => {
                const weightedScore = modelScores[model] / totalSimilarity;
                if (weightedScore > maxScore) {
                    maxScore = weightedScore;
                    bestModel = model;
                }
                return { model, score: weightedScore };
            });
            
            result.sort((a, b) => b.score - a.score);

            logger.info('DB', 'Recommended Model Calculation', { 
                bestModel: result.length > 0 ? result[0].model : 'None',
                scores: result.slice(0, 3) // Log top 3
            });
            
            return result.length > 0 ? result[0].model : null;
            
        } catch (error) {
            logger.error('DB', `Failed to get recommended model`, { error: error.message });
            return null;
        }
    }
    async initializeNewModel(modelName, initialScore) {
        // Insert new model if not exists with count=0
        const query = `INSERT IGNORE INTO model_scores (model_name, score, count) VALUES (?, ?, 0)`;
        
        try {
            const [result] = await pool.execute(query, [modelName, initialScore]);
            if (result.affectedRows > 0) {
                logger.info('DB', `Initialized new model ${modelName} with score ${initialScore}`);
            } else {
                logger.info('DB', `Model ${modelName} already exists, skipping init`);
            }
        } catch (error) {
            logger.error('DB', `Failed to initialize model ${modelName}`, { error: error.message });
            throw error;
        }
    }
    async getModelUsageStats(days = 7) {
        const query = `
            SELECT DATE(created_at) as date, selected_model as model, COUNT(*) as count
            FROM commit_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL ? DAY)
            GROUP BY DATE(created_at), selected_model
            ORDER BY date ASC
        `;
        
        try {
            const [rows] = await pool.execute(query, [days]);
            
            // Format for frontend charts
            const formattedRows = rows.map(r => ({
                date: r.date.toISOString().split('T')[0],
                model: r.model,
                count: r.count
            }));

            return formattedRows;
        } catch (error) {
            logger.error('DB', `Failed to get model usage stats`, { error: error.message });
            throw error;
        }
    }
}

module.exports = new DbService();
