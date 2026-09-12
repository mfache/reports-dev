
<div class="header-with-actions">
    <div>
        <h2>📋 Affectation des Chantiers</h2>
        <p class="hint">Attribution du chargé d'affaires (chantiers.utilisateurs_id) pour chaque chantier.</p>
    </div>
</div>

<div style="display: flex; gap: 20px;">
    <!-- Liste des utilisateurs -->
    <div class="card" style="flex: 1; min-width: 250px;">
        <h3>Utilisateurs</h3>
        <div class="table-scroll" style="max-height: 600px;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Nom / Réf.</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    % for u in users:
                    <tr style="{{'background: var(--surface-light); font-weight: bold;' if str(u['id']) == str(selected_uid) else ''}}">
                        <td>{{u['nom'] or u['ref']}}</td>
                        <td>
                            <a href="{{BASE_PATH}}/admin/chantiers-users?uid={{u['id']}}" class="btn-secondary btn-sm">Sélectionner</a>
                        </td>
                    </tr>
                    % end
                </tbody>
            </table>
        </div>
    </div>

    <!-- Détail des chantiers pour l'utilisateur sélectionné -->
    <div style="flex: 2;">
        % if selected_uid:
        <div class="card" style="margin-bottom: 20px;">
            <h3>Chantiers dont il/elle est chargé(e) d'affaires</h3>
            % if chantiers_utilisateur:
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Chantier</th>
                            <th>Adresse</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        % for c in chantiers_utilisateur:
                        <tr>
                            <td>{{c['ref']}}</td>
                            <td>{{c['adresse'] or '—'}}</td>
                            <td>
                                <form action="{{BASE_PATH}}/admin/chantiers-users/assign" method="POST" style="display:inline;" hx-boost="false">
                                    <input type="hidden" name="uid" value="{{selected_uid}}">
                                    <input type="hidden" name="chantier_id" value="{{c['id']}}">
                                    <select name="new_uid" class="input-dark" style="padding: 2px 5px; font-size: 0.9em; max-width: 150px;" required>
                                        <option value="">-- Réattribuer à --</option>
                                        % for u in users:
                                            % if str(u['id']) != str(selected_uid):
                                            <option value="{{u['id']}}">{{u['nom'] or u['ref']}}</option>
                                            % end
                                        % end
                                    </select>
                                    <button type="submit" class="btn-secondary btn-sm">Réattribuer</button>
                                </form>
                            </td>
                        </tr>
                        % end
                    </tbody>
                </table>
            </div>
            % else:
            <p class="text-muted">Aucun chantier attribué à cet utilisateur.</p>
            % end
        </div>

        <div class="card">
            <h3>Attribuer un chantier existant à cet utilisateur</h3>
            <p class="hint" style="margin-bottom: 10px;">Un chantier ne peut avoir qu'un seul chargé d'affaires : le sélectionner ici le retire automatiquement de son propriétaire actuel.</p>
            <form action="{{BASE_PATH}}/admin/chantiers-users/assign" method="POST" hx-boost="false" style="display: grid; gap: 15px;">
                <input type="hidden" name="uid" value="{{selected_uid}}">
                <input type="hidden" name="new_uid" value="{{selected_uid}}">
                
                <div class="form-group">
                    <label>Chantier</label>
                    <select name="chantier_id" class="input-dark" required>
                        <option value="">-- Choisir un chantier --</option>
                        % for c in chantiers:
                            % if str(c['utilisateurs_id']) != str(selected_uid):
                            <option value="{{c['id']}}">{{c['ref']}} - {{c['adresse'] or ''}} (actuellement : {{c['charge_affaires'] or '—'}})</option>
                            % end
                        % end
                    </select>
                </div>

                <div style="text-align: right;">
                    <button type="submit" class="btn-primary">Attribuer</button>
                </div>
            </form>
        </div>
        % else:
        <div class="card" style="display: flex; align-items: center; justify-content: center; min-height: 200px; color: var(--text-muted);">
            <p>Veuillez sélectionner un utilisateur dans la liste pour gérer ses chantiers.</p>
        </div>
        % end
    </div>
</div>
