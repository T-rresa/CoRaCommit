const dbService = require('../services/dbService');
const logger = require('../services/loggerService');

exports.getModelUsageStats = async (req, res) => {
    try {
        const days = parseInt(req.query.days) || 7;
        const stats = await dbService.getModelUsageStats(days);
        res.json({ status: "success", stats });
    } catch (error) {
        logger.error('API', 'Get stats error', { error: error.message });
        res.status(500).json({ error: "Internal Server Error" });
    }
};
