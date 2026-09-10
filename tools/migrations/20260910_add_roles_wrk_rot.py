#!/usr/bin/python3
"""
Migration : Ajout des colonnes wrk (ouvriers) et rot (superuser) à la table utilisateurs.
"""
import sys
import os

# Ajout du chemin src pour importer core.database
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.database import get_db
import core.config

def migrate(db_label):
    print(f"--- Migration de la base : {db_label} (Fichier: {core.config.DB_ENV_FILE}) ---")
    db = get_db()
    try:
        with db.cursor() as cur:
            # Vérification si les colonnes existent déjà
            cur.execute("DESCRIBE utilisateurs")
            cols = [row['Field'] for row in cur.fetchall()]
            
            if 'wrk' not in cols:
                print("Ajout de la colonne `wrk`...")
                cur.execute("ALTER TABLE utilisateurs ADD COLUMN wrk TINYINT(1) NOT NULL DEFAULT 0 AFTER adm")
            else:
                print("La colonne `wrk` existe déjà.")

            if 'rot' not in cols:
                print("Ajout de la colonne `rot`...")
                cur.execute("ALTER TABLE utilisateurs ADD COLUMN rot TINYINT(1) NOT NULL DEFAULT 0 AFTER wrk")
            else:
                print("La colonne `rot` existe déjà.")

            # Par défaut, Marc (ID 1) devient superuser (rot=1)
            print("Promotion de l'utilisateur ID 1 au rang de superuser (rot=1)...")
            cur.execute("UPDATE utilisateurs SET rot = 1 WHERE id = 1")
            
            db.commit()
            print("Migration terminée avec succès.\n")
    except Exception as e:
        print(f"!! Erreur : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # 1. Base Production
    os.environ['DB_ENV_FILE'] = '/etc/boitier-fleet/db.env'
    # On recharge la config pour prendre en compte le changement d'env
    import importlib
    importlib.reload(core.config)
    migrate("Production (dt)")
    
    # 2. Base Développement
    os.environ['DB_ENV_FILE'] = '/etc/boitier-fleet/db-dev.env'
    importlib.reload(core.config)
    migrate("Développement (dt_dev)")
