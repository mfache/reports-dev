% # Page d'accueil "Poupée Moyenne" (Kinetic Infrastructure)
<div class="header-with-actions">
    <div>
        <h2>📋 Liste des Chantiers</h2>
        <p class="hint">Sélectionnez un chantier pour visualiser les relevés et gérer les équipements.</p>
    </div>
</div>

% if recent_chantiers:
    <div class="nav-label" style="padding-left: 0; margin-bottom: 12px;">
        <span class="material-symbols-outlined icon-label">history</span> Activité Récente
    </div>
    <div class="grid">
        % for c in recent_chantiers:
        <a href="{{BASE_PATH}}/chantier/{{c['id']}}" class="card card-recent luminescent-border" style="border-left: 4px solid var(--tertiary);">
            <h3>
                <span class="text-tertiary">{{c['ref']}}</span>
                % if c.get('active_boitiers', 0) > 0:
                <span class="badge-recent" style="background: rgba(255, 184, 115, 0.1); color: var(--tertiary); border-color: rgba(255, 184, 115, 0.3);">ACTIF</span>
                % else:
                <span class="badge-recent" style="background: rgba(147, 0, 10, 0.18); color: var(--error); border-color: rgba(255, 180, 171, 0.3);">INACTIF &gt; 15"</span>
                % end
            </h3>
            <p><span class="material-symbols-outlined icon-inline">location_on</span> {{c['adresse'] or 'Adresse non renseignée'}}</p>
            <p><span class="material-symbols-outlined icon-inline">person</span> {{c['charge_affaires'] or 'Non assigné'}}</p>
            <div class="meta">
                <span>Modifié le {{c['date_modification'].strftime('%d/%m/%Y')}} à {{c['date_modification'].strftime('%H:%M')}}</span>
            </div>
        </a>
        % end
    </div>
% end

% if current_user['cas'] == 1:
    <h2 style="margin-top: 40px;">📂 Mes Chantiers</h2>
    <div class="grid">
        % if my_chantiers:
            % for c in my_chantiers:
            <a href="{{BASE_PATH}}/chantier/{{c['id']}}" class="card">
                <h3><span class="text-primary">{{c['ref']}}</span></h3>
                <p><span class="material-symbols-outlined icon-inline">location_on</span> {{c['adresse'] or 'Adresse non renseignée'}}</p>
                <div class="meta">
                    <span>Dernière synchro : {{c['date_modification'].strftime('%d/%m/%Y')}}</span>
                </div>
            </a>
            % end
        % else:
            <p class="hint">Aucun chantier ne vous est assigné.</p>
        % end
    </div>
% end

<h2 style="margin-top: 40px;">🏢 {{"Autres Chantiers" if current_user['cas'] == 1 else "Tous les chantiers"}}</h2>
<div class="grid">
    % if other_chantiers:
        % for c in other_chantiers:
        <a href="{{BASE_PATH}}/chantier/{{c['id']}}" class="card">
            <h3><span class="text-primary">{{c['ref']}}</span></h3>
            <p><span class="material-symbols-outlined icon-inline">location_on</span> {{c['adresse'] or 'Adresse non renseignée'}}</p>
            <p><span class="material-symbols-outlined icon-inline">person</span> {{c['charge_affaires'] or 'Non assigné'}}</p>
            <div class="meta">
                <span>{{c['date_modification'].strftime('%d/%m/%Y')}}</span>
            </div>
        </a>
        % end
    % else:
        <p class="hint">Aucun autre chantier trouvé.</p>
    % end
</div>
