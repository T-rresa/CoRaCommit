const axios = require('axios');
const dbService = require('../services/dbService');
const logger = require('../services/loggerService');
const { Worker } = require('bullmq');
const { connection } = require('../config/redis');
const priorityService = require('../services/priorityService');
const {
  EVALUATION_BACKEND_URL,
  EVAL_WORKER_CONCURRENCY,
  EVAL_BUSY_CHECK_INTERVAL_MS
} = require('../config/settings');

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const waitUntilSystemIsReady = async (job) => {
  while (true) {
    const state = await priorityService.getBusyState();
    if (!state.shouldDeferEvaluation) {
      return;
    }

    logger.info('Worker', 'Deferring evaluation while online traffic is prioritized', {
      jobId: job.id,
      activeRequests: state.activeRequests,
      busyFlag: state.busyFlag,
      cpuLoad: Number(state.cpuLoad.toFixed(3))
    });

    await sleep(EVAL_BUSY_CHECK_INTERVAL_MS);
  }
};

const processEvaluation = async (job) => {
  const { feedbackData } = job.data;
  logger.info('Worker', `Processing evaluation job`, { jobId: job.id, sessionId: feedbackData.session_id });

  let dbConnection = null;

    try {
        // Call backend for evaluation
        const evaluationResponse = await axios.post(`${EVALUATION_BACKEND_URL}/api/evaluation/evaluate-multi`, {
      candidates: feedbackData.candidates,
      ground_truth: feedbackData.final_message,
      selected_model: feedbackData.selected_model,
      is_edited: feedbackData.is_edited
        }, { timeout: 30000 });

        const evaluatedCandidates = evaluationResponse.data;
        
        logger.info('Worker', `Received evaluation results`, { 
            sessionId: feedbackData.session_id, 
            candidateCount: evaluatedCandidates.length 
        });

        // Update database with scores
        dbConnection = await dbService.getConnection();
        await dbConnection.beginTransaction();

        try {
            // Batch log evaluation results
            await dbService.logModelEvaluationsBatch(feedbackData.session_id, evaluatedCandidates, dbConnection);

            // Batch update global model scores
            await dbService.updateModelScoresBatch(evaluatedCandidates, dbConnection);

            // Batch update example scores
        if (feedbackData.example_ids && Array.isArray(feedbackData.example_ids) && feedbackData.example_ids.length > 0) {
            await dbService.updateExampleModelScoresBatch(feedbackData.example_ids, evaluatedCandidates, dbConnection);
        }

        await dbConnection.commit();
        logger.info('Worker', `DB Transaction committed`, { sessionId: feedbackData.session_id });

    } catch (dbError) {
        await dbConnection.rollback();
        logger.error('Worker', `DB Transaction failed, rolled back`, { error: dbError.message });
        throw dbError;
    }

    logger.info('Worker', `Evaluation completed successfully`, { sessionId: feedbackData.session_id });
    return evaluatedCandidates;
  } catch (error) {
    logger.error('Worker', `Error processing evaluation job`, { jobId: job.id, error: error.message });
    throw error;
  } finally {
      if (dbConnection) {
          dbConnection.release();
      }
  }
};

const worker = new Worker('evaluation-queue', processEvaluation, { 
    connection,
    concurrency: EVAL_WORKER_CONCURRENCY
});

worker.on('completed', job => {
  logger.info('Worker', `Job completed`, { jobId: job.id });
});

worker.on('failed', (job, err) => {
  logger.error('Worker', `Job failed`, { jobId: job.id, error: err.message });
});

module.exports = worker;
