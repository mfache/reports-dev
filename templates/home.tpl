% rebase('layout.tpl', title='Chantiers - Delta Thermic', current_user=current_user, all_users=all_users)

<div class="container">
    <h1 style="color: var(--text-main); font-size: 1.8em; margin-top: 20px; margin-bottom: 30px;">Accueil - Liste des chantiers</h1>

    <h2>Chantiers Récents</h2>
    <div class="grid">
        % for c in recent_chantiers:
        <a href="/reports/chantier/{{c['id']}}" class="card card-recent">
            <h3><span class="chantier-ref">{{c['ref']}}</span> <span class="badge-recent">Actif</span></h3>
            <p>📍 {{c['adresse'] or 'Adresse non renseignée'}}</p>
            <p>👤 {{c['charge_affaires'] or 'Non assigné'}}</p>
            <div class="meta">
                <span>Modifié le {{c['date_modification'].strftime('%d/%m/%Y')}}</span>
                <span>{{c['date_modification'].strftime('%H:%M')}}</span>
            </div>
        </a>
        % end
    </div>

    % if current_user['cas'] == 1:
    <h2>Mes Chantiers</h2>
    <div class="grid">
        % if my_chantiers:
            % for c in my_chantiers:
            <a href="/reports/chantier/{{c['id']}}" class="card">
                <h3><span class="chantier-ref">{{c['ref']}}</span></h3>
                <p>📍 {{c['adresse'] or 'Adresse non renseignée'}}</p>
                <div class="meta">
                    <span>Modifié le {{c['date_modification'].strftime('%d/%m/%Y')}}</span>
                </div>
            </a>
            % end
        % else:
            <p style="color: var(--text-muted)">Aucun chantier ne vous est assigné.</p>
        % end
    </div>
    % end

    <h2>{{"Autres Chantiers" if current_user['cas'] == 1 else "Autres chantiers"}}</h2>
    <div class="grid">
        % if other_chantiers:
            % for c in other_chantiers:
            <a href="/reports/chantier/{{c['id']}}" class="card">
                <h3><span class="chantier-ref">{{c['ref']}}</span></h3>
                <p>📍 {{c['adresse'] or 'Adresse non renseignée'}}</p>
                <p>👤 {{c['charge_affaires'] or 'Non assigné'}}</p>
                <div class="meta">
                    <span>Modifié le {{c['date_modification'].strftime('%d/%m/%Y')}}</span>
                </div>
            </a>
            % end
        % else:
            <p style="color: var(--text-muted)">Aucun autre chantier trouvé.</p>
        % end
    </div>
</div>
