from db import get_db
db = get_db()
with db.cursor() as cur:
    cur.execute("CREATE TABLE chantier_bacnet_aliases ("
                "id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,"
                "chantier_id INT UNSIGNED NOT NULL,"
                "device_instance VARCHAR(128) NOT NULL,"
                "alias VARCHAR(255) NOT NULL,"
                "updated_by VARCHAR(64),"
                "date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
                "UNIQUE KEY(chantier_id, device_instance),"
                "FOREIGN KEY (chantier_id) REFERENCES chantiers(id) ON DELETE CASCADE"
                ");")
    
    cur.execute("SELECT * FROM boitier_annotations WHERE kind LIKE 'bacnet%'")
    rows = cur.fetchall()
    
    for row in rows:
        # Assuming rpi01 implies chantier_id = 13, but let's be dynamic
        cur.execute("SELECT chantier_id FROM boitier_registre WHERE hostname = %s", (row['updated_by'],))
        res = cur.fetchone()
        chantier_id = res['chantier_id'] if res else 13
        
        cur.execute("INSERT IGNORE INTO chantier_bacnet_aliases (chantier_id, device_instance, alias, updated_by) VALUES (%s, %s, %s, %s)",
                    (chantier_id, row['entry_key'], row['value'], row['updated_by']))
    
    cur.execute("DELETE FROM boitier_annotations WHERE kind LIKE 'bacnet%'")
    cur.execute("RENAME TABLE boitier_annotations TO boitier_fabricants")
