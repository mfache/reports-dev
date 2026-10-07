<div class="header-with-actions">
    <div>
        <h2>👥 Gestion des Utilisateurs</h2>
        <p class="hint">Ajouter, modifier ou archiver des utilisateurs et leurs adresses e-mail.</p>
    </div>
    <button class="btn-primary" onclick="openModal('modal-add-user')">
        <span class="material-symbols-outlined icon-sm">add</span> Ajouter un utilisateur
    </button>
</div>

% if invite_status == 'ok':
<div class="card" style="border-color: var(--success, #2e7d32); margin-bottom: 15px;">
    ✅ Invitation envoyée avec succès.
</div>
% end
% if invite_error:
<div class="card" style="border-color: var(--error); margin-bottom: 15px;">
    ❌ {{invite_error}}
    % if invite_copy_body:
    <div style="margin-top: 10px;">
        <button class="btn-secondary" onclick="openModal('modal-copy-invite')">
            <span class="material-symbols-outlined icon-sm">content_copy</span> Copier le contenu de l'invitation
        </button>
    </div>
    % end
</div>
% end

% if invite_copy_body:
<div id="modal-copy-invite" class="modal" style="display:flex;">
    <div class="modal-content" style="max-width: 600px;">
        <h3>Contenu de l'invitation (envoi email indisponible)</h3>
        <p class="hint">L'envoi automatique par email a echoue. Copiez ce texte et transmettez-le manuellement (autre canal) au destinataire : <strong>{{invite_copy_dest}}</strong>.</p>
        <textarea id="invite-copy-text" class="input-dark" style="width:100%; height:220px; font-family: monospace;" readonly>{{invite_copy_body}}</textarea>
        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;">
            <button type="button" class="btn-secondary" onclick="closeModal('modal-copy-invite')">Fermer</button>
            <button type="button" class="btn-primary" onclick="copyInviteText()">Copier</button>
            % if invite_mailto_url:
            <a class="btn-primary" href="{{invite_mailto_url}}" target="_blank" rel="noopener">
                <span class="material-symbols-outlined icon-sm">mail</span> Ouvrir dans Outlook
            </a>
            % end
        </div>
    </div>
</div>
% end

<div class="card" style="margin-bottom: 30px;">
    <h3>Utilisateurs Actifs</h3>
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
                        <span class="badge" title="Chargé d'affaires">C</span>
                        % end
                        % if user['adm']:
                        <span class="badge" style="background:var(--secondary);color:black;" title="Admin">A</span>
                        % end
                        % if user['wrk']:
                        <span class="badge" title="Ouvrier">W</span>
                        % end
                        % if user['rot']:
                        <span class="badge" style="background:var(--error);color:white;" title="Root">R</span>
                        % end
                        % if user['externe']:
                        <span class="badge" style="background:var(--outline);color:white;" title="Externe / sous-traitant">Ext</span>
                        % end
                        % if user['mobile_valide']:
                        <span class="badge" style="background:#1976d2;color:white;" title="Accès application mobile">M</span>
                        % end
                    </td>
                    <td>
                        <button class="btn-secondary" onclick="editUser({{user['id']}}, '{{user['ref']}}', '{{user['nom'] or ''}}', '{{user['emails'] or ''}}', {{user['cas']}}, {{user['adm']}}, {{user['wrk']}}, {{user['rot']}}, {{user['externe']}}, {{user['mobile_valide']}})">Modifier</button>
                        <a href="{{BASE_PATH}}/admin/chantiers-users?uid={{user['id']}}" class="btn-secondary" style="margin-left:5px;">Chantiers</a>
                        % if user['mobile_valide']:
                        <form action="{{BASE_PATH}}/admin/utilisateurs/{{user['id']}}/mobile-invite" method="POST" style="display:inline;" hx-boost="false">
                            <button type="submit" class="btn-secondary" style="margin-left:5px;" title="Envoyer l'invitation par email">
                                <span class="material-symbols-outlined icon-sm">mail</span> Envoyer un email
                            </button>
                        </form>
                        % end
                    </td>
                </tr>
                % end
                % if not users:
                <tr><td colspan="5" class="text-muted" style="text-align:center;">Aucun utilisateur actif.</td></tr>
                % end
            </tbody>
        </table>
    </div>
</div>

% if archived_users:
<div class="card" style="opacity: 0.85;">
    <h3>Utilisateurs Archivés</h3>
    <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Réf.</th>
                    <th>Nom</th>
                    <th>E-mails</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                % for user in archived_users:
                <tr>
                    <td class="font-mono text-muted">{{user['ref']}}</td>
                    <td class="text-muted">{{user['nom'] or '—'}}</td>
                    <td><span class="text-muted">{{user['emails'] or '—'}}</span></td>
                    <td>
                        <form action="{{BASE_PATH}}/admin/utilisateurs/{{user['id']}}/unarchive" method="POST" style="display:inline;" hx-boost="false">
                            <button type="submit" class="btn-secondary">Restaurer</button>
                        </form>
                    </td>
                </tr>
                % end
            </tbody>
        </table>
    </div>
</div>
% end

<!-- Modal Ajouter -->
<div id="modal-add-user" class="modal">
    <div class="modal-content" style="max-width: 500px;">
        <h3>Ajouter un utilisateur</h3>
        <form action="{{BASE_PATH}}/admin/utilisateurs/edit" method="POST" hx-boost="false">
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
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap;">
                <label><input type="checkbox" name="cas"> CAS</label>
                <label><input type="checkbox" name="adm"> Admin</label>
                <label><input type="checkbox" name="wrk"> Worker</label>
                <label><input type="checkbox" name="rot"> Root</label>
            </div>
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 5px; flex-wrap: wrap;">
                <label><input type="checkbox" name="externe"> Externe / sous-traitant</label>
                <label><input type="checkbox" name="mobile_valide"> Accès application mobile</label>
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
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap;">
                <label><input type="checkbox" id="edit-cas" name="cas"> CAS</label>
                <label><input type="checkbox" id="edit-adm" name="adm"> Admin</label>
                <label><input type="checkbox" id="edit-wrk" name="wrk"> Worker</label>
                <label><input type="checkbox" id="edit-rot" name="rot"> Root</label>
            </div>
            <div class="form-group" style="display: flex; gap: 15px; margin-top: 5px; flex-wrap: wrap;">
                <label><input type="checkbox" id="edit-externe" name="externe"> Externe / sous-traitant</label>
                <label><input type="checkbox" id="edit-mobile_valide" name="mobile_valide"> Accès application mobile</label>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px;">
                <button type="button" class="btn-secondary" style="border-color: var(--error); color: var(--error);" onclick="document.getElementById('form-archive-user').submit();">Archiver</button>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn-secondary" onclick="closeModal('modal-edit-user')">Annuler</button>
                    <button type="submit" class="btn-primary">Enregistrer</button>
                </div>
            </div>
        </form>
        <form id="form-archive-user" method="POST" style="display:none;" hx-boost="false"></form>
    </div>
</div>

<style>
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
.modal-content { background: var(--surface); padding: 25px; border-radius: var(--radius-lg); border: 1px solid var(--outline); width: 100%; }
</style>

<script>
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function copyInviteText() {
    const el = document.getElementById('invite-copy-text');
    el.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(el.value);
    } else {
        document.execCommand('copy');
    }
}
function editUser(id, ref, nom, emails, cas, adm, wrk, rot, externe, mobileValide) {
    document.getElementById('form-edit-user').action = '{{BASE_PATH}}/admin/utilisateurs/' + id + '/update';
    document.getElementById('form-archive-user').action = '{{BASE_PATH}}/admin/utilisateurs/' + id + '/archive';
    document.getElementById('edit-ref').value = ref;
    document.getElementById('edit-nom').value = nom;
    document.getElementById('edit-emails').value = emails;
    document.getElementById('edit-cas').checked = !!cas;
    document.getElementById('edit-adm').checked = !!adm;
    document.getElementById('edit-wrk').checked = !!wrk;
    document.getElementById('edit-rot').checked = !!rot;
    document.getElementById('edit-externe').checked = !!externe;
    document.getElementById('edit-mobile_valide').checked = !!mobileValide;
    openModal('modal-edit-user');
}
</script>
