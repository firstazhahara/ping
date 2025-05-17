A Python GUI application for monitoring network connectivity to multiple targets with PostgreSQL storage and automatic data retention.

Features
Concurrent Pinging: Monitors all targets simultaneously using thread pooling

Database Storage: Stores results in PostgreSQL with automatic cleanup (TTL)

Reliable Monitoring: Multiple ping attempts and DNS fallback to reduce false negatives

Real-time Dashboard: Color-coded status display with detailed metrics

Historical Data: Tracks success rates over 24-hour periods

Dark Mode UI: Modern dark theme with purple accent colors

Configurable Settings: Adjustable ping attempts, timeouts, and data retention

Requirements
Python 3.7+

PostgreSQL database

Required packages:

pip install psycopg2-binary ping3 matplotlib
Database Setup
Create the required tables in PostgreSQL:

sql
CREATE TABLE IF NOT EXISTS ping_targets (
    id SERIAL PRIMARY KEY,
    target VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ping_results (
    id SERIAL PRIMARY KEY,
    target VARCHAR(255) NOT NULL,
    status BOOLEAN NOT NULL,
    response_time FLOAT,
    attempts INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ping_results_timestamp ON ping_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_ping_results_target ON ping_results(target);

-- Create automatic cleanup function
CREATE OR REPLACE FUNCTION clean_old_ping_results()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM ping_results 
    WHERE timestamp < NOW() - INTERVAL '30 days';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create cleanup trigger
DROP TRIGGER IF EXISTS trigger_clean_old_ping_results ON ping_results;
CREATE TRIGGER trigger_clean_old_ping_results
AFTER INSERT ON ping_results
EXECUTE FUNCTION clean_old_ping_results();
Configuration
Edit the database connection parameters in the code:

python
self.db_params = {
    "host": "your-database-host",
    "database": "your-database-name",
    "user": "your-username",
    "password": "your-password"
}
Usage
Add targets using the "Add Target" button

Click "Start Monitoring" to begin pinging

View real-time status in the dashboard

Adjust settings as needed:

Ping attempts (default: 2)

Ping timeout (default: 2 seconds)

Data retention period (default: 30 days)

Features in Detail
Target Management:

Add/remove multiple IPs or hostnames

Persistent storage in database

Monitoring:

Concurrent pinging of all targets

Configurable 3-second interval

Multiple attempts per target

Data Visualization:

Color-coded online/offline status

Response time tracking

24-hour success rate calculation

Database:

Automatic cleanup of old records

Efficient storage of ping results

Troubleshooting
If you encounter connection issues:

Verify database credentials

Check network connectivity to database host

Ensure PostgreSQL is running and accessible

For ping reliability issues:

Increase ping attempts in settings

Adjust timeout values

Check network firewall settings

License
This project is licensed under the MIT License - see the LICENSE file for details.
