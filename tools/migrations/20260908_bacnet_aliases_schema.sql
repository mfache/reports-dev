CREATE TABLE chantier_bacnet_aliases (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    chantier_id INT UNSIGNED NOT NULL,
    device_instance VARCHAR(128) NOT NULL,
    alias VARCHAR(255) NOT NULL,
    updated_by VARCHAR(64),
    date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY(chantier_id, device_instance),
    FOREIGN KEY (chantier_id) REFERENCES chantiers(id) ON DELETE CASCADE
);

INSERT INTO chantier_bacnet_aliases (chantier_id, device_instance, alias, updated_by)
SELECT 
    IFNULL((SELECT chantier_id FROM boitier_registre WHERE hostname = boitier_annotations.updated_by LIMIT 1), 13),
    entry_key, 
    value, 
    updated_by
FROM boitier_annotations
WHERE kind LIKE 'bacnet%';

DELETE FROM boitier_annotations WHERE kind LIKE 'bacnet%';

RENAME TABLE boitier_annotations TO boitier_fabricants;
