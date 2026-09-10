#!/usr/bin/python3
"""
Migration : Ajout de la table utilisateurs_emails pour supporter plusieurs adresses par utilisateur.
"""
import sys
import os

# Ajout du chemin src pour importer core.database
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.database import get_db

def migrate():
    db = get_db()
    try:
        with db.cursor() as cur:
            print("==> Création de la table `utilisateurs_emails`...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS utilisateurs_emails (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    utilisateur_id INT UNSIGNED NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY (email),
                    INDEX (utilisateur_id),
                    CONSTRAINT fk_email_utilisateur FOREIGN KEY (utilisateur_id) 
                        REFERENCES utilisateurs(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Ajout de l'email connu pour Marc Fache (ID 1)
            print("==> Insertion de l'email par défaut pour Marc...")
            cur.execute("""
                INSERT IGNORE INTO utilisateurs_emails (utilisateur_id, email) 
                VALUES (1, 'marc@fache.be')
            """)
            
            db.commit()
            print("==> Migration terminée avec succès.")
    except Exception as e:
        print(f"!! Erreur lors de la migration : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
