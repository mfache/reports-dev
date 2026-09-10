RENAME TABLE boitier_annotations TO boitier_fabricants;

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

-- Migrate existing bacnet aliases from boitier_fabricants to chantier_bacnet_aliases
-- Wait, we don't have chantier_id in boitier_fabricants. We might not be able to migrate them safely unless we know the chantier.
-- Let's check if there are any existing records.
