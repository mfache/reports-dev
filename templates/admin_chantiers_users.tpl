
<div class="header-with-actions">
    <div>
        <h2>📋 Affectation des Chantiers</h2>
        <p class="hint">Attribution des chantiers aux utilisateurs (gestion des filtres).</p>
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

    <!-- Détail des filtres pour l'utilisateur sélectionné -->
    <div style="flex: 2;">
        % if selected_uid:
        <div class="card" style="margin-bottom: 20px;">
            <h3>Filtres / Chantiers attribués</h3>
            % if filtres:
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Chantier</th>
                            <th>Filtre (Réf)</th>
                            <th>Description</th>
                            <th>Ordre</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        % for f in filtres:
                        <tr>
                            <td>{{f['chantier_ref']}}</td>
                            <td>{{f['filtre_ref']}}</td>
                            <td>{{f['description'] or '—'}}</td>
                            <td>{{f['tri']}}</td>
                            <td>
                                <form action="{{BASE_PATH}}/admin/chantiers-users/delete/{{f['id']}}" method="POST" style="display:inline;" hx-boost="false">
                                    <input type="hidden" name="uid" value="{{selected_uid}}">
                                    <button type="submit" class="btn-secondary btn-sm" style="color: var(--error); border-color: var(--error);">Supprimer</button>
                                </form>
                            </td>
                        </tr>
                        % end
                    </tbody>
                </table>
            </div>
            % else:
            <p class="text-muted">Aucun filtre attribué à cet utilisateur.</p>
            % end
        </div>

        <div class="card">
            <h3>Ajouter un filtre (Chantier)</h3>
            <form action="{{BASE_PATH}}/admin/chantiers-users/add" method="POST" hx-boost="false" style="display: grid; gap: 15px;">
                <input type="hidden" name="uid" value="{{selected_uid}}">
                
                <div class="form-group">
                    <label>Chantier</label>
                    <select name="chantier_id" class="input-dark" required>
                        <option value="">-- Choisir un chantier --</option>
                        % for c in chantiers:
                        <option value="{{c['id']}}">{{c['ref']}} - {{c['adresse'] or ''}}</option>
                        % end
                    </select>
                </div>

                <div style="display: flex; gap: 15px;">
                    <div class="form-group" style="flex: 1;">
                        <label>Référence du Filtre</label>
                        <input type="text" name="filtre_ref" class="input-dark" required placeholder="Ex: Notes, Accès...">
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Ordre (Tri)</label>
                        <input type="number" name="tri" class="input-dark" value="0">
                    </div>
                </div>

                <div class="form-group">
                    <label>Description</label>
                    <input type="text" name="description" class="input-dark" placeholder="Description courte (optionnel)">
                </div>

                <div style="text-align: right;">
                    <button type="submit" class="btn-primary">Ajouter</button>
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
