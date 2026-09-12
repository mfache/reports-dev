
<div class="header-with-actions">
    <div>
        <h2>👥 Gestion des Utilisateurs</h2>
        <p class="hint">Ajouter, modifier ou supprimer des utilisateurs et leurs adresses e-mail.</p>
    </div>
    <button class="btn-primary" onclick="openModal('modal-add-user')">
        <span class="material-symbols-outlined icon-sm">add</span> Ajouter un utilisateur
    </button>
</div>

<div class="card">
    <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Réf.</th>
                    <th>Nom</th>
                    <th>E-mails</th>
                    <th>Droits</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                % for user in users:
                <tr>
                    <td class="font-mono text-primary">{{user['ref']}}</td>
                    <td>{{user['nom'] or '—'}}</td>
                    <td>
                        % if user['emails']:
                            % for email in user['emails'].split(', '):
                                <div class="nav-label" style="display:inline-block; margin: 2px; padding: 2px 6px;">{{email}}</div>
                            % end
                        % else:
                            <span class="text-muted">—</span>
                        % end
                    </td>
                    <td>
                        % if user['cas']:
                        <span class="badge" title="CAS">C</span>
                        % end
                        % if user['adm']:
                        <span class="badge" style="background:var(--secondary);color:black;" title="Admin">A</span>
                        % end
                        % if user['wrk']:
                        <span class="badge" title="Worker">W</span>
                        % end
                        % if user['rot']:
                        <span class="badge" style="background:var(--error);color:white;" title="Root">R</span>
                        % end
                    </td>
                    <td>
                        <button class="btn-secondary" onclick="editUser({{user['id']}}, '{{user['ref']}}', '{{user['nom'] or ''}}', '{{user['emails'] or ''}}', {{user['cas']}}, {{user['adm']}}, {{user['wrk']}}, {{user['rot']}})">Modifier</button>
                        <form action="{{BASE_PATH}}/admin/utilisateurs/{{user['id']}}/delete" method="POST" style="display:inline;" onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cet utilisateur ?');">
                            <button type="submit" class="btn-secondary" style="border-color: var(--error); color: var(--error);">Supprimer</button>
                        </form>
                    </td>
                </tr>
                % end
            </tbody>
        </table>
    </div>
</div>

<!-- Modal Ajouter -->
<div id="modal-add-user" class="modal">
    <div class="modal-content" style="max-width: 500px;">
        <h3>Ajouter un utilisateur</h3>
        <form action="{{BASE_PATH}}/admin/utilisateurs" method="POST" hx-boost="false">
            <div class="form-group">
                <label>Référence (ex: usr_xxx)</label>
                <input type="text" name="ref" class="input-dark" required>
            </div>
            <div class="form-group">
                <label>Nom complet</label>
                <input type="text" name="nom" class="input-dark">
            </div>
            <div class="form-group">
                <label>E-mails (séparés par des virgules)</label>
                <input type="text" name="emails" class="input-dark" placeholder="jean@example.com, paul@example.com">
            </div>
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 15px;">
                <label><input type="checkbox" name="cas"> CAS</label>
                <label><input type="checkbox" name="adm"> Admin</label>
                <label><input type="checkbox" name="wrk"> Worker</label>
                <label><input type="checkbox" name="rot"> Root</label>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                <button type="button" class="btn-secondary" onclick="closeModal('modal-add-user')">Annuler</button>
                <button type="submit" class="btn-primary">Ajouter</button>
            </div>
        </form>
    </div>
</div>

<!-- Modal Modifier -->
<div id="modal-edit-user" class="modal">
    <div class="modal-content" style="max-width: 500px;">
        <h3>Modifier l'utilisateur</h3>
        <form id="form-edit-user" method="POST" hx-boost="false">
            <div class="form-group">
                <label>Référence</label>
                <input type="text" id="edit-ref" name="ref" class="input-dark" required>
            </div>
            <div class="form-group">
                <label>Nom complet</label>
                <input type="text" id="edit-nom" name="nom" class="input-dark">
            </div>
            <div class="form-group">
                <label>E-mails (séparés par des virgules)</label>
                <input type="text" id="edit-emails" name="emails" class="input-dark">
            </div>
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 15px;">
                <label><input type="checkbox" id="edit-cas" name="cas"> CAS</label>
                <label><input type="checkbox" id="edit-adm" name="adm"> Admin</label>
                <label><input type="checkbox" id="edit-wrk" name="wrk"> Worker</label>
                <label><input type="checkbox" id="edit-rot" name="rot"> Root</label>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                <button type="button" class="btn-secondary" onclick="closeModal('modal-edit-user')">Annuler</button>
                <button type="submit" class="btn-primary">Enregistrer</button>
            </div>
        </form>
    </div>
</div>

<style>
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
.modal-content { background: var(--surface); padding: 25px; border-radius: var(--radius-lg); border: 1px solid var(--outline); width: 100%; }
</style>

<script>
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function editUser(id, ref, nom, emails, cas, adm, wrk, rot) {
    document.getElementById('form-edit-user').action = '{{BASE_PATH}}/admin/utilisateurs/' + id + '/update';
    document.getElementById('edit-ref').value = ref;
    document.getElementById('edit-nom').value = nom;
    document.getElementById('edit-emails').value = emails;
    document.getElementById('edit-cas').checked = !!cas;
    document.getElementById('edit-adm').checked = !!adm;
    document.getElementById('edit-wrk').checked = !!wrk;
    document.getElementById('edit-rot').checked = !!rot;
    openModal('modal-edit-user');
}
</script>
