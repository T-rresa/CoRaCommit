const os = require('os');
const { redisClient } = require('../config/redis');
const logger = require('./loggerService');
const {
    ONLINE_ACTIVE_REQUEST_KEY,
    ONLINE_BUSY_FLAG_KEY,
    ONLINE_BUSY_TTL_SECONDS,
    EVAL_CPU_THRESHOLD
} = require('../config/settings');

class PriorityService {
    async markGenerationStarted() {
        if (!redisClient) return;
        try {
            const multi = redisClient.multi();
            multi.incr(ONLINE_ACTIVE_REQUEST_KEY);
            multi.set(ONLINE_BUSY_FLAG_KEY, '1', 'EX', ONLINE_BUSY_TTL_SECONDS);
            await multi.exec();
        } catch (error) {
            logger.warn('Priority', 'Failed to mark generation start', { error: error.message });
        }
    }

    async markGenerationFinished() {
        if (!redisClient) return;
        try {
            const current = await redisClient.decr(ONLINE_ACTIVE_REQUEST_KEY);
            if (current <= 0) {
                const multi = redisClient.multi();
                multi.set(ONLINE_ACTIVE_REQUEST_KEY, 0);
                multi.del(ONLINE_BUSY_FLAG_KEY);
                await multi.exec();
            }
        } catch (error) {
            logger.warn('Priority', 'Failed to mark generation finish', { error: error.message });
        }
    }

    getNormalizedCpuLoad() {
        const cpuCount = os.cpus()?.length || 1;
        const loadAverage = os.loadavg?.()[0] || 0;
        if (!loadAverage || cpuCount <= 0) {
            return 0;
        }
        return loadAverage / cpuCount;
    }

    async getBusyState() {
        const cpuLoad = this.getNormalizedCpuLoad();
        let activeRequests = 0;
        let busyFlag = false;

        if (redisClient) {
            try {
                const [activeValue, busyValue] = await Promise.all([
                    redisClient.get(ONLINE_ACTIVE_REQUEST_KEY),
                    redisClient.get(ONLINE_BUSY_FLAG_KEY)
                ]);
                activeRequests = parseInt(activeValue || '0', 10);
                busyFlag = busyValue === '1';
            } catch (error) {
                logger.warn('Priority', 'Failed to read busy state from Redis', { error: error.message });
            }
        }

        const cpuBusy = cpuLoad >= EVAL_CPU_THRESHOLD;
        return {
            activeRequests,
            busyFlag,
            cpuLoad,
            cpuBusy,
            shouldDeferEvaluation: busyFlag || activeRequests > 0 || cpuBusy
        };
    }
}

module.exports = new PriorityService();
