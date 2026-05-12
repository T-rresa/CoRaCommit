const dbService = require('../services/dbService');
const logger = require('../services/loggerService');
const { evaluationQueue, redisClient } = require('../config/redis');
const { EVAL_JOB_DELAY_MS } = require('../config/settings');

exports.saveFeedback = async (req, res) => {
    try {
        const data = req.body;
        
        // Basic Validation
        if (!data.user_id || !data.final_message) {
            return res.status(400).json({ error: "Missing required fields" });
        }

        const result = await dbService.saveCommitFeedback(data);
        const session_id = result.insertId;

        // Optimization: Reduce payload size in Redis
        // Instead of sending full diff or large text, we rely on session_id or just send essential data
        // For evaluation worker, we need: candidates, final_message, selected_model, is_edited, example_ids
        // We can keep sending them for now as they are not huge, but good to be aware.
        
        // Add to evaluation queue
        await evaluationQueue.add(
            'evaluate-feedback',
            { feedbackData: { ...data, session_id } },
            {
                delay: EVAL_JOB_DELAY_MS,
                removeOnComplete: 1000,
                removeOnFail: 2000
            }
        );
        logger.info('API', 'Feedback added to evaluation queue', { session_id });

        res.json({ status: "success", message: "Feedback saved and queued for evaluation", session_id });
    } catch (error) {
        logger.error('API', 'Feedback save error', { error: error.message });
        res.status(500).json({ error: "Internal Server Error" });
    }
};

exports.getModelRankings = async (req, res) => {
    try {
        let formattedRankings = [];
        let redisFailed = false;
        
        try {
            // Try to get from Redis first
            const rankings = await redisClient.zrevrange('model_rankings', 0, 9, 'WITHSCORES');
            
            if (rankings && rankings.length > 0) {
                for (let i = 0; i < rankings.length; i += 2) {
                    formattedRankings.push({
                        model: rankings[i],
                        score: parseFloat(rankings[i + 1])
                    });
                }
            }
        } catch (redisError) {
            logger.error('API', 'Redis get rankings error, falling back to DB', { error: redisError.message });
            redisFailed = true;
        }
        
        // If Redis failed or returned empty, get from DB
        if (formattedRankings.length === 0) {
            const dbRankings = await dbService.getModelRankingsFromDB();
            formattedRankings = dbRankings.map(row => ({
                model: row.model,
                score: parseFloat(row.score)
            }));
            
            // Auto-recovery: If we successfully got data from DB but Redis failed/was empty, try to repopulate Redis
            if (formattedRankings.length > 0) {
                 // Do this asynchronously to not block response
                 (async () => {
                     try {
                         // We can't easily check if Redis is back up if the error was connection refused, 
                         // but we can try-catch the set operation.
                         // Use pipeline for atomic update of the whole leaderboard
                         const pipeline = redisClient.pipeline();
                         
                         // Clear old key first to avoid stale data mixing? 
                         // Or just overwrite. ZADD updates existing scores.
                         // If we want to remove models that no longer exist (unlikely), we might delete key first.
                         // For safety, let's just ZADD.
                         
                         for (const rank of formattedRankings) {
                             pipeline.zadd('model_rankings', rank.score, rank.model);
                         }
                         
                         // Also cache individual scores
                         for (const rank of formattedRankings) {
                             pipeline.set(`model_score:${rank.model}`, rank.score);
                         }
                         
                         await pipeline.exec();
                         logger.info('API', 'Repopulated Redis model rankings from DB');
                     } catch (repopulateError) {
                         // Silent fail, just log debug
                         logger.debug('API', 'Failed to repopulate Redis', { error: repopulateError.message });
                     }
                 })();
            }
        }
        
        res.json({ status: "success", rankings: formattedRankings });
    } catch (error) {
        logger.error('API', 'Get rankings error', { error: error.message });
        res.status(500).json({ error: "Internal Server Error" });
    }
};
