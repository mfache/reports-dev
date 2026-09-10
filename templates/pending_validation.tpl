% # Page d'attente de validation "Poupée Moyenne" (Kinetic Infrastructure)
<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; text-align: center; padding: 20px;">
    <div style="font-size: 5rem; margin-bottom: 20px; animation: pulse 2s infinite;">⏳</div>
    <h2 style="color: var(--tertiary); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px;">Accès en attente</h2>
    
    <div class="card luminescent-border" style="max-width: 500px; padding: 40px; margin-top: 20px;">
        <p style="font-size: 1.1rem; line-height: 1.6; margin-bottom: 30px;">
            Bonjour <strong class="text-primary">{{current_user['nom']}}</strong>,<br><br>
            Votre compte a été créé suite à votre authentification Google. 
            Cependant, un <strong>administrateur</strong> doit valider votre rôle (CA ou Admin) avant de libérer l'accès aux données.
        </p>
        <div style="padding-top: 20px; border-top: 1px solid var(--outline-variant); color: var(--on-surface-variant); font-size: 0.85rem;">
            Veuillez contacter <strong>Marc Fache</strong> pour l'activation.
        </div>
    </div>
</div>

<style>
@keyframes pulse {
    0% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.1); opacity: 1; }
    100% { transform: scale(1); opacity: 0.8; }
}
</style>
