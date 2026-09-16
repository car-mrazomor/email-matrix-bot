CREATE DATABASE email_matrix_data;
USE email_matrix_data;

CREATE TABLE IF NOT EXISTS data (
    subject         VARCHAR(555),
    from_           VARCHAR(555),
    date_           VARCHAR(555),
    body            LONGTEXT,
    filename        VARCHAR(555),
    payload         VARCHAR(555),
    orig_message_id VARCHAR(555),
    orig_references VARCHAR(555),
    event_id        VARCHAR(555),
    tnxId           VARCHAR(555)
)ENGINE=INNODB;