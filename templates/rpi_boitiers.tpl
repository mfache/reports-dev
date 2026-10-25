% # Page « Boîtiers » : choix d'un boîtier à ouvrir via le proxy de docs
<div class="header-with-actions">
    <div>
        <h2>🛰️ Boîtiers</h2>
        <p class="hint">Ouvrir l'interface d'un boîtier, sans VPN ni application à installer.</p>
    </div>
</div>

% if refus:
<div class="card" style="border-left: 4px solid var(--error); margin-bottom: 20px;">
    Accès refusé au boîtier <strong>{{refus}}</strong> : il ne fait pas partie de vos boîtiers autorisés,
    ou il n'est pas joignable en ce moment.
</div>
% end

% if not autorise:
<div class="card" style="max-width: 560px;">
    <p>Votre compte n'a pas encore accès aux boîtiers.</p>
    <p class="hint">Un administrateur doit cocher « M » (accès boîtiers) sur votre fiche,
    dans Administration &gt; Utilisateurs.</p>
</div>
% elif not boitiers:
<div class="card" style="max-width: 560px;">
    <p>Aucun boîtier n'est associé à vos chantiers pour le moment.</p>
</div>
% else:
<table class="data-table">
    <thead>
        <tr><th>Boîtier</th><th>Chantier</th><th>État</th><th></th></tr>
    </thead>
    <tbody>
    % for b in boitiers:
        <tr>
            <td><strong>{{b['hostname']}}</strong></td>
            <td>{{b['chantier_ref'] or '—'}}</td>
            <td>
                % if b['en_ligne']:
                <span class="text-secondary">● En ligne</span>
                % else:
                <span class="hint">○ Hors ligne</span>
                % end
            </td>
            <td>
                % if b['joignable']:
                <a href="{{b['url']}}" class="btn-secondary" hx-boost="false" target="_blank" rel="noopener">Ouvrir</a>
                % else:
                <span class="hint">Non joignable</span>
                % end
            </td>
        </tr>
    % end
    </tbody>
</table>
% end
