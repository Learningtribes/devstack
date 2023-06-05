CREATE DATABASE IF NOT EXISTS credentials;
CREATE USER IF NOT EXISTS 'credentials001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON credentials.* TO 'credentials001'@'%';

CREATE DATABASE IF NOT EXISTS discovery;
CREATE USER IF NOT EXISTS 'discov001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON discovery.* TO 'discov001'@'%';

CREATE DATABASE IF NOT EXISTS ecommerce;
CREATE USER IF NOT EXISTS 'ecomm001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON ecommerce.* TO 'ecomm001'@'%';

CREATE DATABASE IF NOT EXISTS edxmktg;
CREATE USER IF NOT EXISTS 'edxmktg001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON edxmktg.* TO 'edxmktg001'@'%';

CREATE DATABASE IF NOT EXISTS notes;
CREATE USER IF NOT EXISTS 'notes001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON notes.* TO 'notes001'@'%';

CREATE DATABASE IF NOT EXISTS edxapp;
CREATE DATABASE IF NOT EXISTS edxapp_csmh;
CREATE USER IF NOT EXISTS 'edxapp001'@'%' IDENTIFIED BY 'password';
GRANT ALL ON edxapp.* TO 'edxapp001'@'%';
GRANT ALL ON edxapp_csmh.* TO 'edxapp001'@'%';

FLUSH PRIVILEGES;


-- ALTER USER 'credentials001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
-- ALTER USER 'discov001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
-- ALTER USER 'ecomm001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
-- ALTER USER 'edxmktg001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
-- ALTER USER 'notes001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
-- ALTER USER 'edxapp001'@'%' IDENTIFIED WITH mysql_native_password BY 'password';