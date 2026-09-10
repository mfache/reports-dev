% # Page Maintenance Templates "Poupée Moyenne" (Kinetic Infrastructure)
<div class="header-with-actions">
    <div>
        <h2>📦 Maintenance des Templates Modbus</h2>
        <p class="hint">Gestion du versioning immuable et cartographie d'usage sur la flotte.</p>
    </div>
    <div style="min-width: 300px;">
        <div style="position: relative;">
            <span class="material-symbols-outlined" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--outline);">search</span>
            <input type="text" id="tpl-search" placeholder="Filtrer les modèles..." onkeyup="filterTemplates(this.value)" class="input-dark" style="padding-left: 35px;">
        </div>
    </div>
</div>

<div id="alert-box" style="display: none; margin-bottom: 24px;"></div>

<div class="table-scroll">
    <table class="data-table" id="templates-table">
        <thead>
            <tr>
                <th>Modèle / Fabricant</th>
                <th style="text-align: center;">V.</th>
                <th>Auteur (Node)</th>
                <th style="text-align: center;">Usage</th>
                <th>Détails Usage</th>
                <th>Dernière Modif</th>
                <th style="text-align: center;">Actions</th>
            </tr>
        </thead>
        <tbody>
            % for t_uuid, t_data in templates_by_uuid.items():
                % for rev in t_data['revisions']:
                <tr class="template-row {{'text-muted' if rev['is_deprecated'] else ''}}" data-name="{{rev['name'].lower()}}" data-manufacturer="{{rev['manufacturer'].lower()}}">
                    <td>
                        <div style="font-weight: 700;" class="{{'text-muted' if rev['is_deprecated'] else 'text-primary'}}">
                            {{rev['name']}}
                            % if rev['is_deprecated']:
                                <span class="badge-recent" style="font-size: 0.6rem; vertical-align: middle; margin-left: 5px; background: rgba(255,184,115,0.05); color: var(--tertiary); border-color: rgba(255,184,115,0.2);">DÉPRÉCIÉ</span>
                            % end
                        </div>
                        <div style="font-size: 0.75rem; color: var(--outline);">{{rev['manufacturer'] or '—'}}</div>
                    </td>
                    <td style="text-align: center;"><span class="font-mono">v{{rev['version']}}</span></td>
                    <td class="font-mono text-muted" style="font-size: 0.8rem;">{{rev['created_by_node']}}</td>
                    <td style="text-align: center;">
                        <span class="badge-recent" style="background: {{'rgba(76,215,246,0.1)' if rev['active_boitiers_count'] > 0 else 'transparent'}}; color: {{'var(--primary)' if rev['active_boitiers_count'] > 0 else 'var(--outline)'}};">
                            {{rev['active_boitiers_count']}} node(s)
                        </span>
                    </td>
                    <td style="font-size: 0.75rem; max-width: 250px;" class="text-muted">
                        {{rev['device_details'] or 'Non utilisé'}}
                    </td>
                    <td class="text-muted">{{format_human_date(rev['date_modification'])}}</td>
                    <td style="text-align: center;">
                        <div style="display: flex; gap: 8px; justify-content: center;">
                            <button onclick="toggleDeprecate('{{rev['revision_uuid']}}')" class="btn-icon btn-sm" title="{{'Restaurer' if rev['is_deprecated'] else 'Déprécier'}}">
                                <span class="material-symbols-outlined">{{'settings_backup_restore' if rev['is_deprecated'] else 'archive'}}</span>
                            </button>
                            % if rev['active_boitiers_count'] == 0:
                            <button onclick="deleteRevision('{{rev['revision_uuid']}}')" class="btn-icon btn-icon-danger btn-sm" title="Supprimer">
                                <span class="material-symbols-outlined">delete</span>
                            </button>
                            % end
                        </div>
                    </td>
                </tr>
                % end
            % end
        </tbody>
    </table>
</div>

<script>
async function toggleDeprecate(revUuid) {
    try {
        const res = await fetch('{{BASE_PATH}}/maintenance/templates/toggle_deprecate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ revision_uuid: revUuid })
        });
        if (res.ok) window.location.reload();
    } catch (e) { alert("Erreur réseau"); }
}

async function deleteRevision(revUuid) {
    if (!confirm("Supprimer définitivement cette révision ?")) return;
    try {
        const res = await fetch('{{BASE_PATH}}/maintenance/templates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ revision_uuid: revUuid })
        });
        const data = await res.json();
        if (res.ok) window.location.reload(); else alert(data.error);
    } catch (e) { alert("Erreur réseau"); }
}

function filterTemplates(q) {
    const query = q.toLowerCase();
    document.querySelectorAll('.template-row').forEach(row => {
        const match = row.dataset.name.includes(query) || row.dataset.manufacturer.includes(query);
        row.style.display = match ? '' : 'none';
    });
}
</script>
