// node_service/src/config/redis.js
const { Queue } = require('bullmq');
const IORedis = require('ioredis');

const connection = {
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  maxRetriesPerRequest: null, // Required for BullMQ
  retryStrategy: function(times) {
    // Retry with exponential backoff, max 2 seconds
    const delay = Math.min(times * 50, 2000);
    return delay;
  }
};

let redisClient;
let evaluationQueue;

try {
  redisClient = new IORedis(connection);
  
  redisClient.on('error', (err) => {
    // Prevent unhandled error events from crashing the process
    console.error('Redis Client Error:', err.code || err.message);
  });

  evaluationQueue = new Queue('evaluation-queue', { 
    connection,
    // Add default job options or other queue settings here
  });
  
  evaluationQueue.on('error', (err) => {
      console.error('Queue Error:', err.message);
  });
  
} catch (error) {
  console.error('Failed to initialize Redis:', error.message);
  // We can provide mock objects or throw, depending on how strict we want to be
}

module.exports = {
  connection,
  evaluationQueue,
  redisClient
};
