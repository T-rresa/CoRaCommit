const pool = require('../config/db');
const logger = require('./loggerService');
const { AVAILABLE_MODELS } = require('../config/settings');

const CREATE_TABLE_SQL = `
    CREATE TABLE IF NOT EXISTS model_registry (
        model_name VARCHAR(255) PRIMARY KEY,
        description VARCHAR(255) DEFAULT '',
        family VARCHAR(64) NOT NULL,
        base_url VARCHAR(512) NOT NULL,
        available BOOLEAN DEFAULT TRUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
`;

class ModelRegistryService {
    constructor() {
        this._initialized = false;
        this._initPromise = null;
    }

    async ensureRegistryReady() {
        if (this._initialized) return;
        if (this._initPromise) return this._initPromise;

        this._initPromise = (async () => {
            const connection = await pool.getConnection();
            try {
                await connection.query(CREATE_TABLE_SQL);
                const values = AVAILABLE_MODELS.map(model => [
                    model.name,
                    model.description || '',
                    model.family || 'gpt',
                    model.base_url || 'https://api.openai.com/v1',
                    model.available !== false
                ]);

                if (values.length > 0) {
                    await connection.query(
                        `INSERT INTO model_registry (model_name, description, family, base_url, available)
                         VALUES ?
                         ON DUPLICATE KEY UPDATE
                           description = VALUES(description),
                           family = VALUES(family),
                           base_url = VALUES(base_url),
                           available = VALUES(available)`,
                        [values]
                    );
                }
                this._initialized = true;
            } catch (error) {
                logger.error('ModelRegistry', 'Failed to initialize model registry table', { error: error.message });
                throw error;
            } finally {
                connection.release();
            }
        })();

        return this._initPromise;
    }

    async getAvailableModels() {
        await this.ensureRegistryReady();
        const [rows] = await pool.execute(
            `SELECT 
                model_name AS name,
                description,
                family,
                base_url,
                available
             FROM model_registry
             WHERE available = TRUE
             ORDER BY created_at ASC, model_name ASC`
        );
        return rows;
    }

    async getModelByName(modelName) {
        await this.ensureRegistryReady();
        const [rows] = await pool.execute(
            `SELECT 
                model_name AS name,
                description,
                family,
                base_url,
                available
             FROM model_registry
             WHERE model_name = ?
             LIMIT 1`,
            [modelName]
        );
        return rows[0] || null;
    }

    async registerModel({ model_name, description = '', family, base_url, available = true, initial_score = 0.6 }) {
        if (!model_name) throw new Error('model_name is required');
        if (!family) throw new Error('family is required');
        if (!base_url) throw new Error('base_url is required');

        await this.ensureRegistryReady();
        const connection = await pool.getConnection();
        try {
            await connection.beginTransaction();

            await connection.execute(
                `INSERT INTO model_registry (model_name, description, family, base_url, available)
                 VALUES (?, ?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                   description = VALUES(description),
                   family = VALUES(family),
                   base_url = VALUES(base_url),
                   available = VALUES(available)`,
                [model_name, description, family, base_url, available]
            );

            await connection.execute(
                `INSERT INTO model_scores (model_name, score, count)
                 VALUES (?, ?, 0)
                 ON DUPLICATE KEY UPDATE model_name = VALUES(model_name)`,
                [model_name, initial_score]
            );

            await connection.commit();
            logger.info('ModelRegistry', 'Model registered', { model_name, family, base_url, available });
            return { success: true, model_name };
        } catch (error) {
            await connection.rollback();
            logger.error('ModelRegistry', 'Failed to register model', { model_name, error: error.message });
            throw error;
        } finally {
            connection.release();
        }
    }
}

module.exports = new ModelRegistryService();
