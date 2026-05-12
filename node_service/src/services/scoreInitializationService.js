const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { promisify } = require('util');
const { execFile } = require('child_process');
const pool = require('../config/db');
const logger = require('./loggerService');

const execFileAsync = promisify(execFile);

class ScoreInitializationService {
    getResourcePath() {
        return process.env.RESOURCE_PATH || path.resolve(__dirname, '../../resource');
    }

    async getExampleIdsFromDbScores() {
        const [rows] = await pool.execute('SELECT DISTINCT example_id FROM example_model_scores');
        const existingIds = rows
            .map(row => row.example_id)
            .filter(id => id !== null && id !== undefined && id !== '');

        logger.info('ScoreInit', `Loaded ${existingIds.length} example ids from example_model_scores`);
        return existingIds;
    }

    async getExampleIdsFromDocsDb() {
        const resourcePath = this.getResourcePath();
        const docsDbPath = path.join(resourcePath, 'docs.db');

        if (!fs.existsSync(docsDbPath)) {
            logger.warn('ScoreInit', `docs.db not found at ${docsDbPath}`);
            return [];
        }

        logger.info('ScoreInit', `Reading example ids from ${docsDbPath}`);

        const { stdout } = await execFileAsync('sqlite3', [
            docsDbPath,
            'SELECT id FROM docs;'
        ]);

        const ids = stdout
            .split(/\r?\n/)
            .map(line => line.trim())
            .filter(line => line.length > 0);

        logger.info('ScoreInit', `Loaded ${ids.length} example ids from docs.db`);
        return ids;
    }

    async getExampleIdsFromDocsJsonl() {
        const resourcePath = this.getResourcePath();
        const docsPath = path.join(resourcePath, 'docs.jsonl');
        const ids = [];

        logger.info('ScoreInit', `Reading docs from ${docsPath}`);

        const fileStream = fs.createReadStream(docsPath);
        const rl = readline.createInterface({
            input: fileStream,
            crlfDelay: Infinity
        });

        for await (const line of rl) {
            if (!line.trim()) continue;
            try {
                const doc = JSON.parse(line);
                if (doc._id !== undefined) {
                    ids.push(String(doc._id));
                }
            } catch (e) {
                logger.warn('ScoreInit', 'Failed to parse line in docs.jsonl', { error: e.message });
            }
        }

        logger.info('ScoreInit', `Loaded ${ids.length} example ids from docs.jsonl`);
        return ids;
    }

    /**
     * Resolve all example IDs.
     * Priority:
     * 1. existing example_model_scores table
     * 2. docs.db
     * 3. docs.jsonl
     */
    async getExampleIds() {
        try {
            const existingIds = await this.getExampleIdsFromDbScores();
            if (existingIds.length > 0) {
                return existingIds;
            }
        } catch (dbError) {
            logger.warn('ScoreInit', 'Failed to read existing example ids from example_model_scores', {
                error: dbError.message
            });
        }

        try {
            const docsDbIds = await this.getExampleIdsFromDocsDb();
            if (docsDbIds.length > 0) {
                return docsDbIds;
            }
        } catch (docsDbError) {
            logger.warn('ScoreInit', 'Failed to read example ids from docs.db', {
                error: docsDbError.message
            });
        }

        try {
            const docsJsonIds = await this.getExampleIdsFromDocsJsonl();
            if (docsJsonIds.length > 0) {
                return docsJsonIds;
            }
        } catch (jsonlError) {
            logger.error('ScoreInit', 'Failed to read docs.jsonl', { error: jsonlError.message });
            throw jsonlError;
        }

        return [];
    }

    async initializeScores(targetModelName, initialScore = 0.6) {
        if (!targetModelName) {
            throw new Error('Model name is required for initialization');
        }

        const exampleIds = await this.getExampleIds();

        if (exampleIds.length === 0) {
            logger.warn('ScoreInit', 'No examples found for score initialization');
            return { count: 0, message: 'No examples found' };
        }

        logger.info('ScoreInit', `Initializing scores for model: ${targetModelName} across ${exampleIds.length} examples`);

        let totalInserted = 0;
        const connection = await pool.getConnection();

        try {
            await connection.beginTransaction();
            const chunkSize = 1000;

            for (let i = 0; i < exampleIds.length; i += chunkSize) {
                const chunk = exampleIds.slice(i, i + chunkSize);
                const values = chunk.map(id => [id, targetModelName, initialScore]);

                if (values.length > 0) {
                    const query = `
                        INSERT IGNORE INTO example_model_scores (example_id, model_name, score)
                        VALUES ?
                    `;
                    const [result] = await connection.query(query, [values]);
                    totalInserted += result.affectedRows;
                }
            }

            await connection.commit();
            logger.info('ScoreInit', 'Initialization complete', { totalInserted });
            return {
                success: true,
                message: 'Scores initialized successfully',
                details: {
                    models: [targetModelName],
                    examplesCount: exampleIds.length,
                    insertedRows: totalInserted
                }
            };
        } catch (error) {
            await connection.rollback();
            logger.error('ScoreInit', 'Transaction failed', { error: error.message });
            throw error;
        } finally {
            connection.release();
        }
    }
}

module.exports = new ScoreInitializationService();
