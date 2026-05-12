const mysql = require('mysql2/promise');
require('dotenv').config();

const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '123456',
    database: process.env.DB_NAME || 'auto_gen_message',
    multipleStatements: true // Allow multiple SQL statements
};

async function initSchema() {
    console.log('Initializing database schema...');
    
    let connection;
    try {
        // First connect without database to create it if not exists
        const sysConfig = { ...dbConfig, database: undefined };
        connection = await mysql.createConnection(sysConfig);
        
        await connection.query(`CREATE DATABASE IF NOT EXISTS ${dbConfig.database}`);
        console.log(`Database ${dbConfig.database} created or already exists.`);
        
        await connection.end();
        
        // Now connect to the specific database
        connection = await mysql.createConnection(dbConfig);
        
        const schema = `
            CREATE TABLE IF NOT EXISTS commit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                models_requested JSON,
                candidates JSON,
                selected_model VARCHAR(255),
                final_message TEXT,
                is_edited BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                example_ids JSON,
                diff MEDIUMTEXT
            );

            CREATE TABLE IF NOT EXISTS model_scores (
                model_name VARCHAR(255) PRIMARY KEY,
                score FLOAT DEFAULT 0.6,
                count INT DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS model_registry (
                model_name VARCHAR(255) PRIMARY KEY,
                description VARCHAR(255) DEFAULT '',
                family VARCHAR(64) NOT NULL,
                base_url VARCHAR(512) NOT NULL,
                available BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evaluation_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT,
                model_name VARCHAR(255),
                semantic_score FLOAT,
                lexical_score FLOAT,
                sim_score FLOAT,
                user_preference FLOAT,
                single_score FLOAT,
                compare_score FLOAT,
                final_score FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES commit_logs(id)
            );

            CREATE TABLE IF NOT EXISTS example_model_scores (
                example_id VARCHAR(255),
                model_name VARCHAR(255),
                score FLOAT DEFAULT 0.0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (example_id, model_name)
            );
        `;

        await connection.query(schema);
        console.log('✅ Tables created successfully.');
        
    } catch (error) {
        console.error('❌ Schema initialization failed:', error.message);
    } finally {
        if (connection) await connection.end();
        process.exit();
    }
}

initSchema();
