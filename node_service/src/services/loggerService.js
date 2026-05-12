// node_service/src/services/loggerService.js
const fs = require('fs');
const path = require('path');

class LoggerService {
    constructor() {
        this.logDir = path.join(__dirname, '../../logs');
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }
        this.logFile = path.join(this.logDir, 'app.log');
    }

    _write(level, category, message, meta = {}) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            category,
            message,
            ...meta
        };
        const logString = JSON.stringify(logEntry) + '\n';
        
        // Output to console
        console.log(`[${timestamp}] [${level.toUpperCase()}] [${category}] ${message}`, Object.keys(meta).length ? JSON.stringify(meta) : '');

        // Output to file
        fs.appendFile(this.logFile, logString, (err) => {
            if (err) console.error('Failed to write log:', err);
        });
    }

    info(categoryOrMessage, messageOrMeta, meta) {
        let category = 'General';
        let msg = categoryOrMessage;
        let metadata = messageOrMeta;

        if (typeof messageOrMeta === 'string') {
            category = categoryOrMessage;
            msg = messageOrMeta;
            metadata = meta;
        } else if (typeof categoryOrMessage === 'string' && typeof messageOrMeta === 'object') {
             // Handle info("Msg", {meta}) -> category=General
             // Handle info("Category", "Msg") -> category=Category, msg=Msg
        }

        // Standardize: If 3 args, explicit category. If 2 args and 2nd is string, explicit category.
        // Simplified signature for internal usage: info(category, message, meta)
        // To be safe and backward compatible:
        // 1. info(message, meta) -> category='General'
        // 2. info(category, message, meta)
        
        if (arguments.length >= 3 || (arguments.length === 2 && typeof arguments[1] === 'string')) {
             this._write('info', arguments[0], arguments[1], arguments[2] || {});
        } else {
             this._write('info', 'General', arguments[0], arguments[1] || {});
        }
    }

    error(categoryOrMessage, messageOrMeta, meta) {
        if (arguments.length >= 3 || (arguments.length === 2 && typeof arguments[1] === 'string')) {
             this._write('error', arguments[0], arguments[1], arguments[2] || {});
        } else {
             this._write('error', 'General', arguments[0], arguments[1] || {});
        }
    }

    warn(categoryOrMessage, messageOrMeta, meta) {
        if (arguments.length >= 3 || (arguments.length === 2 && typeof arguments[1] === 'string')) {
             this._write('warn', arguments[0], arguments[1], arguments[2] || {});
        } else {
             this._write('warn', 'General', arguments[0], arguments[1] || {});
        }
    }
}

module.exports = new LoggerService();
