% # Page d'attente de validation "Poupée Moyenne"
<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; text-align: center; padding: 20px;">
    <div style="font-size: 5em; margin-bottom: 20px;">⏳</div>
    <h1 style="color: var(--accent-orange); margin-bottom: 10px;">Accès en attente de validation</h1>
    <div style="background: var(--card-bg); border: 1px solid var(--border-color); padding: 30px; border-radius: 12px; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3);">
        <p style="font-size: 1.1em; line-height: 1.6; margin-bottom: 20px;">
            Bonjour <strong>{{current_user['nom']}}</strong>,<br><br>
            Votre compte a été créé automatiquement suite à votre première connexion. 
            Cependant, un administrateur doit valider votre profil (Chargé d'Affaires ou Admin) avant que vous ne puissiez accéder aux données de la flotte.
        </p>
        <p style="color: var(--text-muted); font-size: 0.9em; border-top: 1px solid var(--border-color); pt: 20px;">
            Veuillez contacter Marc Fache pour activer votre accès.
        </p>
    </div>
</div>
