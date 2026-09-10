% rebase('layout.tpl', title='Maintenance des Templates - Delta Thermic')
<div class="container" style="max-width: 1300px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
        <div>
            <h1 style="color: var(--text-main); font-size: 1.8em; margin: 0 0 5px 0;">📦 Maintenance des Templates Modbus</h1>
            <p style="color: var(--text-muted); margin: 0;">Gestion du versioning immuable, télémétrie d'usage sur la flotte et inspection des diffs.</p>
        </div>
        <div style="display: flex; gap: 10px;">
            <input type="text" id="tpl-search" placeholder="🔍 Filtrer les modèles..." onkeyup="filterTemplates(this.value)" style="background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); padding: 8px 14px; border-radius: 6px; font-size: 0.95em;">
        </div>
    </div>

    <!-- Alert / notification box -->
    <div id="alert-box" style="display: none; padding: 12px 18px; border-radius: 6px; margin-bottom: 20px; font-weight: 500;"></div>

    % for t_uuid, tpl in templates_by_uuid.items():
    <div class="card tpl-card" data-name="{{tpl['name'].lower()}}" data-mfr="{{(tpl['manufacturer'] or '').lower()}}" style="margin-bottom: 25px; padding: 20px; border-left: 4px solid var(--accent-cyan);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 15px; margin-bottom: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px;">
            <div>
                <h3 style="margin: 0 0 6px 0; color: var(--accent-cyan); font-size: 1.3em;">
                    {{tpl['name']}}
                    % if tpl['manufacturer']:
                        <span style="font-size: 0.75em; color: var(--text-muted); font-weight: normal; margin-left: 8px;">({{tpl['manufacturer']}})</span>
                    % end
                </h3>
                <div style="font-family: monospace; font-size: 0.8em; color: var(--text-muted);">
                    UUID: {{t_uuid}} &nbsp;•&nbsp; 
                    <span style="color: {{'#22c55e' if tpl['total_active_boitiers'] > 0 else '#94a3b8'}};">
                        <strong>{{tpl['total_active_boitiers']}}</strong> boîtier(s) actif(s) ({{tpl['total_active_devices']}} équipement(s))
                    </span>
                </div>
            </div>
            <div>
                % if len(tpl['revisions']) > 1:
                <button class="btn" style="padding: 6px 12px; font-size: 0.85em;" onclick="openDiffModal('{{t_uuid}}')">
                    🔍 Comparer les versions (Diff)
                </button>
                % end
            </div>
        </div>

        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 0.9em; background: rgba(0,0,0,0.15); border-radius: 6px; overflow: hidden;">
                <thead>
                    <tr style="background: rgba(255,255,255,0.05); color: var(--text-muted); text-align: left;">
                        <th style="padding: 10px 12px;">Version</th>
                        <th style="padding: 10px 12px;">Révision UUID</th>
                        <th style="padding: 10px 12px;">Auteur (Nœud)</th>
                        <th style="padding: 10px 12px;">Points</th>
                        <th style="padding: 10px 12px;">Date</th>
                        <th style="padding: 10px 12px;">Usage Flotte</th>
                        <th style="padding: 10px 12px;">Statut</th>
                        <th style="padding: 10px 12px; text-align: right;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    % for rev in tpl['revisions']:
                    <tr style="border-top: 1px solid var(--border-color);">
                        <td style="padding: 10px 12px; font-weight: bold;">
                            <span style="background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); padding: 2px 8px; border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.3);">
                                v{{rev['version']}}
                            </span>
                        </td>
                        <td style="padding: 10px 12px; font-family: monospace; font-size: 0.85em; color: var(--text-muted);" title="{{rev['revision_uuid']}}">
                            {{rev['revision_uuid'][:10]}}...
                        </td>
                        <td style="padding: 10px 12px;">
                            <span style="font-family: monospace; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">
                                {{rev['created_by_node']}}
                            </span>
                        </td>
                        <td style="padding: 10px 12px;">
                            <span style="background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">{{rev['reads_count']}} reg.</span>
                        </td>
                        <td style="padding: 10px 12px; color: var(--text-muted); font-size: 0.85em;">
                            {{format_human_date(rev['date_creation'])}}
                        </td>
                        <td style="padding: 10px 12px;">
                            % if rev['active_boitiers_count'] > 0:
                                <span style="background: rgba(34, 197, 94, 0.15); color: #22c55e; padding: 3px 8px; border-radius: 12px; border: 1px solid rgba(34, 197, 94, 0.3); font-weight: bold; font-size: 0.85em;" title="Boîtiers: {{rev['using_boitiers']}} | Détails: {{rev['device_details']}}">
                                    ● {{rev['active_boitiers_count']}} actif(s)
                                </span>
                            % else:
                                <span style="color: var(--text-muted); font-size: 0.85em;">0 actif</span>
                            % end
                        </td>
                        <td style="padding: 10px 12px;">
                            % if rev['is_deprecated']:
                                <span style="background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 2px 8px; border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 0.8em;">
                                    ⚠️ Déprécié
                                </span>
                            % else:
                                <span style="background: rgba(34, 197, 94, 0.1); color: #22c55e; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">
                                    ✓ Stable
                                </span>
                            % end
                        </td>
                        <td style="padding: 10px 12px; text-align: right;">
                            <div style="display: inline-flex; gap: 6px;">
                                <button class="btn" style="padding: 4px 8px; font-size: 0.8em;" onclick="toggleDeprecate('{{rev['revision_uuid']}}')" title="Basculer statut déprécié">
                                    {{'Réactiver' if rev['is_deprecated'] else 'Déprécier'}}
                                </button>
                                % if rev['active_boitiers_count'] == 0:
                                <button class="btn" style="padding: 4px 8px; font-size: 0.8em; border-color: #ef4444; color: #ef4444;" onclick="deleteRevision('{{rev['revision_uuid']}}', '{{tpl['name']}} v{{rev['version']}}')" title="Supprimer cette version (0 boîtier actif)">
                                    🗑️ Supprimer
                                </button>
                                % else:
                                <button class="btn" style="padding: 4px 8px; font-size: 0.8em; border-color: #64748b; color: #64748b; opacity: 0.6; cursor: not-allowed;" onclick="alert('Suppression impossible : {{rev['active_boitiers_count']}} boîtier(s) utilisent activement cette version ({{rev['using_boitiers']}}).')" title="Suppression verrouillée : des boîtiers l\'utilisent">
                                    🔒 Verrouillé
                                </button>
                                % end
                            </div>
                        </td>
                    </tr>
                    % end
                </tbody>
            </table>
        </div>
    </div>
    % end
</div>

<!-- Modal Diff Visualizer -->
<div id="diff-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.75); z-index: 10000; align-items: center; justify-content: center; backdrop-filter: blur(3px);">
    <div style="background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; width: 950px; max-width: 95vw; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
        
        <!-- Header -->
        <div style="padding: 16px 20px; background: var(--header-bg); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
            <h3 id="diff-modal-title" style="margin: 0; color: var(--accent-cyan); font-size: 1.2em;">🔍 Comparaison de Versions</h3>
            <button onclick="closeDiffModal()" style="background: transparent; border: none; color: var(--text-muted); font-size: 1.5em; cursor: pointer; padding: 0 5px;">&times;</button>
        </div>

        <!-- Version Selectors -->
        <div style="padding: 14px 20px; background: rgba(0,0,0,0.2); border-bottom: 1px solid var(--border-color); display: flex; gap: 20px; align-items: center; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 220px;">
                <label style="font-size: 0.85em; color: var(--text-muted); display: block; margin-bottom: 4px;">Version Source (A) :</label>
                <select id="diff-select-v1" onchange="runDiff()" style="width: 100%; background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px;"></select>
            </div>
            <div style="font-size: 1.3em; color: var(--text-muted); padding-top: 15px;">➔</div>
            <div style="flex: 1; min-width: 220px;">
                <label style="font-size: 0.85em; color: var(--text-muted); display: block; margin-bottom: 4px;">Version Cible (B) :</label>
                <select id="diff-select-v2" onchange="runDiff()" style="width: 100%; background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px;"></select>
            </div>
            <div style="padding-top: 18px;">
                <label style="font-size: 0.85em; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; gap: 6px;">
                    <input type="checkbox" id="diff-only-changes" onchange="renderDiffResults()"> Uniquement les différences
                </label>
            </div>
        </div>

        <!-- Diff Summary & Container -->
        <div id="diff-content" style="padding: 20px; overflow-y: auto; flex: 1;">
            <div style="text-align: center; color: var(--text-muted); padding: 30px;">Sélectionnez deux versions pour afficher les différences.</div>
        </div>
    </div>
</div>

<script>
const templatesData = {{!templates_data_json}};
let currentDiffData = null;

function filterTemplates(query) {
    query = query.toLowerCase().trim();
    document.querySelectorAll('.tpl-card').forEach(card => {
        const name = card.getAttribute('data-name') || '';
        const mfr = card.getAttribute('data-mfr') || '';
        if (name.includes(query) || mfr.includes(query)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

function showAlert(msg, isError = false) {
    const box = document.getElementById('alert-box');
    box.style.display = 'block';
    box.style.background = isError ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)';
    box.style.color = isError ? '#ef4444' : '#22c55e';
    box.style.border = isError ? '1px solid #ef4444' : '1px solid #22c55e';
    box.innerText = msg;
    setTimeout(() => { box.style.display = 'none'; }, 6000);
}

async function toggleDeprecate(revUuid) {
    try {
        const res = await fetch('/reports/maintenance/templates/toggle_deprecate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ revision_uuid: revUuid })
        });
        const data = await res.json();
        if (data.ok) {
            window.location.reload();
        } else {
            showAlert(data.error || 'Erreur lors du changement de statut', true);
        }
    } catch (e) {
        showAlert('Erreur de communication : ' + e, true);
    }
}

async function deleteRevision(revUuid, label) {
    if (!confirm(`Confirmez-vous la suppression définitive de la révision "${label}" ?\nCette action est irréversible.`)) {
        return;
    }
    try {
        const res = await fetch('/reports/maintenance/templates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ revision_uuid: revUuid })
        });
        const data = await res.json();
        if (data.ok) {
            showAlert(data.message || 'Révision supprimée avec succès.');
            window.location.reload();
        } else {
            showAlert(data.error || 'Impossible de supprimer cette version', true);
        }
    } catch (e) {
        showAlert('Erreur réseau : ' + e, true);
    }
}

function openDiffModal(tplUuid) {
    const tpl = templatesData[tplUuid];
    if (!tpl || tpl.revisions.length < 2) return;

    document.getElementById('diff-modal-title').innerText = `🔍 Comparaison des révisions : ${tpl.name}`;
    const s1 = document.getElementById('diff-select-v1');
    const s2 = document.getElementById('diff-select-v2');
    s1.innerHTML = '';
    s2.innerHTML = '';

    tpl.revisions.forEach((rev, idx) => {
        const opt1 = document.createElement('option');
        opt1.value = rev.revision_uuid;
        opt1.text = `v${rev.version} (${rev.created_by_node}) - ${rev.revision_uuid.substring(0, 8)}`;
        if (idx === 1) opt1.selected = true;
        s1.appendChild(opt1);

        const opt2 = document.createElement('option');
        opt2.value = rev.revision_uuid;
        opt2.text = `v${rev.version} (${rev.created_by_node}) - ${rev.revision_uuid.substring(0, 8)}`;
        if (idx === 0) opt2.selected = true;
        s2.appendChild(opt2);
    });

    document.getElementById('diff-modal').style.display = 'flex';
    runDiff();
}

function closeDiffModal() {
    document.getElementById('diff-modal').style.display = 'none';
}

async function runDiff() {
    const rev1 = document.getElementById('diff-select-v1').value;
    const rev2 = document.getElementById('diff-select-v2').value;
    const container = document.getElementById('diff-content');

    if (!rev1 || !rev2) return;

    container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted);">Calcul du diff en cours...</div>';

    try {
        const res = await fetch(`/reports/maintenance/templates/diff-data?rev1=${rev1}&rev2=${rev2}`);
        const data = await res.json();
        if (data.ok) {
            currentDiffData = data;
            renderDiffResults();
        } else {
            container.innerHTML = `<div style="color:#ef4444; padding:20px;">Erreur : ${data.error}</div>`;
        }
    } catch (e) {
        container.innerHTML = `<div style="color:#ef4444; padding:20px;">Erreur de communication : ${e}</div>`;
    }
}

function renderDiffResults() {
    if (!currentDiffData) return;
    const diff = currentDiffData.diff;
    const rev1 = currentDiffData.rev1;
    const rev2 = currentDiffData.rev2;
    const container = document.getElementById('diff-content');
    const onlyChanges = document.getElementById('diff-only-changes').checked;

    let html = `
        <div style="display:flex; gap:15px; margin-bottom:20px; flex-wrap:wrap;">
            <div style="flex:1; background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border:1px solid var(--border-color);">
                <strong style="color:var(--text-main);">Source (v${rev1.version}) :</strong> <span style="font-family:monospace; color:var(--text-muted);">${rev1.created_by_node}</span>
                <div style="font-size:0.85em; color:var(--text-muted); margin-top:4px;">${rev1.reads_count} registre(s)</div>
            </div>
            <div style="flex:1; background:rgba(255,255,255,0.03); padding:12px; border-radius:6px; border:1px solid var(--border-color);">
                <strong style="color:var(--text-main);">Cible (v${rev2.version}) :</strong> <span style="font-family:monospace; color:var(--text-muted);">${rev2.created_by_node}</span>
                <div style="font-size:0.85em; color:var(--text-muted); margin-top:4px;">${rev2.reads_count} registre(s)</div>
            </div>
        </div>

        <div style="display:flex; gap:10px; margin-bottom:15px; font-size:0.85em;">
            <span style="background:rgba(34,197,94,0.15); color:#22c55e; padding:3px 8px; border-radius:4px;">+ ${diff.added_count} Ajouté(s)</span>
            <span style="background:rgba(239,68,68,0.15); color:#ef4444; padding:3px 8px; border-radius:4px;">- ${diff.removed_count} Supprimé(s)</span>
            <span style="background:rgba(245,158,11,0.15); color:#f59e0b; padding:3px 8px; border-radius:4px;">~ ${diff.modified_count} Modifié(s)</span>
            <span style="background:rgba(255,255,255,0.05); color:var(--text-muted); padding:3px 8px; border-radius:4px;">= ${diff.unchanged_count} Identique(s)</span>
        </div>
    `;

    if (Object.keys(diff.meta_changes).length > 0) {
        html += `<div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:6px; padding:10px 14px; margin-bottom:15px; font-size:0.85em;">
            <strong style="color:#f59e0b;">Changements de métadonnées :</strong><br>`;
        for (const [k, chg] of Object.entries(diff.meta_changes)) {
            html += `• <strong>${k}</strong> : <code>${chg.old}</code> ➔ <code>${chg.new}</code><br>`;
        }
        html += `</div>`;
    }

    html += `
        <table style="width:100%; border-collapse:collapse; font-size:0.85em;">
            <thead>
                <tr style="background:rgba(255,255,255,0.05); color:var(--text-muted); text-align:left;">
                    <th style="padding:8px 10px;">Statut</th>
                    <th style="padding:8px 10px;">FC</th>
                    <th style="padding:8px 10px;">Adresse</th>
                    <th style="padding:8px 10px;">Libellé</th>
                    <th style="padding:8px 10px;">Type</th>
                    <th style="padding:8px 10px;">Échelle</th>
                    <th style="padding:8px 10px;">Unité</th>
                </tr>
            </thead>
            <tbody>
    `;

    let shownCount = 0;
    diff.registers.forEach(r => {
        if (onlyChanges && r.status === 'unchanged') return;
        shownCount++;

        let bg = 'transparent';
        let badge = '';
        let rowDetails = '';

        if (r.status === 'added') {
            bg = 'rgba(34, 197, 94, 0.12)';
            badge = '<span style="color:#22c55e; font-weight:bold;">+ Ajouté</span>';
        } else if (r.status === 'removed') {
            bg = 'rgba(239, 68, 68, 0.12)';
            badge = '<span style="color:#ef4444; font-weight:bold;">- Supprimé</span>';
        } else if (r.status === 'modified') {
            bg = 'rgba(245, 158, 11, 0.12)';
            badge = '<span style="color:#f59e0b; font-weight:bold;">~ Modifié</span>';
            const changesList = [];
            for (const [prop, val] of Object.entries(r.changes)) {
                changesList.push(`${prop}: <s>${val.old}</s> ➔ <strong>${val.new}</strong>`);
            }
            rowDetails = `<div style="font-size:0.8em; color:#f59e0b; margin-top:3px;">${changesList.join(' | ')}</div>`;
        } else {
            badge = '<span style="color:var(--text-muted);">= Identique</span>';
        }

        html += `
            <tr style="background:${bg}; border-top:1px solid var(--border-color);">
                <td style="padding:8px 10px;">${badge}</td>
                <td style="padding:8px 10px;">FC0${r.function}</td>
                <td style="padding:8px 10px; font-family:monospace; font-weight:bold;">${r.reg}</td>
                <td style="padding:8px 10px;"><strong>${r.name}</strong>${rowDetails}</td>
                <td style="padding:8px 10px;">${r.type}</td>
                <td style="padding:8px 10px;">${r.scale}</td>
                <td style="padding:8px 10px;">${r.unit || '—'}</td>
            </tr>
        `;
    });

    if (shownCount === 0) {
        html += `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-muted);">Aucune différence entre ces deux versions.</td></tr>`;
    }

    html += `</tbody></table>`;
    container.innerHTML = html;
}
</script>
