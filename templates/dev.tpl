% # Page Développeur "Poupée Moyenne" (Kinetic Infrastructure)
<div class="header-with-actions">
    <div>
        <h2>🛠️ Espace Développeur</h2>
        <p class="hint">Outils de diagnostic, introspection de la base de données et documentation API.</p>
    
    <div style="display: flex; align-items: center; gap: 15px;">
        <div id="sim-status" style="font-family: var(--font-mono); font-size: 0.85rem; padding: 6px 12px; border-radius: 20px; background: rgba(255,255,255,0.1); color: var(--text-muted); display: flex; align-items: center; gap: 8px;">
            <span class="material-symbols-outlined icon-sm">sync</span> Chargement...
        </div>
        <button id="sim-btn" onclick="toggleSimulator()" class="btn-primary" style="background: var(--surface-low); border: 1px solid var(--outline); color: var(--text); padding: 8px 16px;">
            <span class="material-symbols-outlined icon-sm">sensors</span> 
            <span id="sim-btn-text">Démarrer Simulateur</span>
        </button>
    </div>

    <script>
    async function checkSimStatus() {
        try {
            const res = await fetch('{{BASE_PATH}}/dev/simulator/status');
            const data = await res.json();
            updateSimUI(data.status);
        } catch (e) {
            console.error("Erreur checkSimStatus", e);
        }
    }

    function updateSimUI(status) {
        const statusEl = document.getElementById('sim-status');
        const btnText = document.getElementById('sim-btn-text');
        
        if (status === 'started') {
            statusEl.innerHTML = '<span class="material-symbols-outlined icon-sm" style="color: var(--secondary);">graphic_eq</span> Simulateur Actif';
            statusEl.style.background = 'rgba(74, 225, 118, 0.1)';
            statusEl.style.color = 'var(--secondary)';
            btnText.innerText = 'Arrêter Simulateur';
        } else {
            statusEl.innerHTML = '<span class="material-symbols-outlined icon-sm">sync_disabled</span> Simulateur Arrêté';
            statusEl.style.background = 'rgba(255, 255, 255, 0.1)';
            statusEl.style.color = 'var(--text-muted)';
            btnText.innerText = 'Démarrer Simulateur';
        }
    }

    async function toggleSimulator() {
        const btn = document.getElementById('sim-btn');
        btn.disabled = true;
        try {
            const res = await fetch('{{BASE_PATH}}/dev/simulator/toggle', { method: 'POST' });
            const data = await res.json();
            updateSimUI(data.status);
        } catch (e) {
            alert("Erreur réseau");
        }
        btn.disabled = false;
    }

    // Vérifier l'état au chargement de la page
    window.addEventListener('DOMContentLoaded', checkSimStatus);
    </script>
</div>
</div>

<div class="nav-tabs" style="border-left: none; background: var(--surface-low); margin-bottom: 24px; padding: 5px; border-radius: var(--radius-lg); display: inline-flex; gap: 5px;">
    <a href="?tab=sql" class="{{'tab-active' if tab == 'sql' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">SQL & DB</a>
    <a href="?tab=api" class="{{'tab-active' if tab == 'api' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">Doc API</a>
    <a href="?tab=env" class="{{'tab-active' if tab == 'env' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">Système</a>
    <a href="?tab=deploy" class="{{'tab-active' if tab == 'deploy' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">Déploiement</a>
</div>

% if tab == 'sql':
    <div class="card luminescent-border">
        <h3 style="margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <span class="material-symbols-outlined text-primary">terminal</span>
            Console SQL Interactive
        </h3>
        <p class="hint">Exécutez des requêtes MariaDB directement sur la base <code>{{'dt_dev' if BASE_PATH != '/reports' else 'dt'}}</code>.</p>
        
        <div class="form-group" style="margin-top: 20px;">
            <textarea id="sql-query" placeholder="SELECT * FROM chantiers LIMIT 5;" class="input-dark" style="height: 120px; font-size: 1rem;"></textarea>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <button onclick="executeSQL()" class="btn-primary">
                <span class="material-symbols-outlined icon-sm">play_arrow</span> Exécuter
            </button>
        </div>
        <div id="sql-result" style="margin-top: 24px; overflow-x: auto;"></div>
    </div>

    <script>
    async function executeSQL() {
        const query = document.getElementById('sql-query').value.trim();
        const resultDiv = document.getElementById('sql-result');
        if (!query) return;

        resultDiv.innerHTML = '<div class="hint">Chargement des résultats...</div>';

        try {
            const res = await fetch('{{BASE_PATH}}/sql', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            const data = await res.json();

            if (data.error) {
                resultDiv.innerHTML = `<div class="card" style="border-color: var(--error); background: rgba(147, 0, 10, 0.1); color: var(--error);"><span class="material-symbols-outlined icon-inline">error</span> ${data.error}</div>`;
            } else if (data.message) {
                resultDiv.innerHTML = `<div class="card" style="border-color: var(--secondary); background: rgba(74, 225, 118, 0.1); color: var(--secondary);"><span class="material-symbols-outlined icon-inline">check_circle</span> ${data.message}</div>`;
            } else if (data.columns && data.rows) {
                if (data.rows.length === 0) {
                    resultDiv.innerHTML = '<div class="hint">Requête exécutée avec succès : 0 résultat.</div>';
                } else {
                    let tableHtml = `<div class="nav-label"><span class="material-symbols-outlined icon-label">table_rows</span> ${data.rows.length} lignes récupérées</div>`;
                    tableHtml += '<div class="table-scroll"><table class="data-table"><thead><tr>';
                    data.columns.forEach(col => { tableHtml += `<th>${col}</th>`; });
                    tableHtml += '</tr></thead><tbody>';
                    data.rows.forEach(row => {
                        tableHtml += '<tr>';
                        data.columns.forEach(col => {
                            let val = row[col];
                            if (val === null) val = '<small class="text-muted">NULL</small>';
                            tableHtml += `<td class="font-mono" style="font-size: 0.8rem;">${val}</td>`;
                        });
                        tableHtml += '</tr>';
                    });
                    tableHtml += '</tbody></table></div>';
                    resultDiv.innerHTML = tableHtml;
                }
            }
        } catch (e) {
            resultDiv.innerHTML = `<div class="card" style="border-color: var(--error); color: var(--error);">Erreur réseau : ${e.message}</div>`;
        }
    }
    </script>

    <h2 style="margin-top: 48px;">📊 Schéma de la Base de Données</h2>
    <div class="card" style="background: white; color: black; display: flex; justify-content: center; padding: 40px;">
        <div class="mermaid">
    {{!mermaid_code}}
        </div>
    </div>
    <!-- Mermaid JS Integration -->
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
    </script>

    <h2 style="margin-top: 48px;">📚 Liste des Tables ({{len(tables)}})</h2>
    % for table, cols in tables_info.items():
        <div class="card">
            <h3 style="display: flex; align-items: center; gap: 10px;">
                <span class="material-symbols-outlined text-secondary">table</span>
                <code>{{table}}</code>
            </h3>
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr><th>Champ</th><th>Type</th><th>Null</th><th>Clé</th><th>Défaut</th><th>Extra</th></tr>
                    </thead>
                    <tbody>
                        % for col in cols:
                        <tr>
                            <td class="font-mono text-primary">{{col['Field']}}</td>
                            <td class="font-mono text-muted" style="font-size: 0.75rem;">{{col['Type']}}</td>
                            <td>{{col['Null']}}</td>
                            <td><span class="text-tertiary" style="font-weight: 700;">{{col['Key']}}</span></td>
                            <td class="text-muted">{{col['Default'] or '—'}}</td>
                            <td class="text-muted"><small>{{col['Extra']}}</small></td>
                        </tr>
                        % end
                    </tbody>
                </table>
            </div>
        </div>
    % end

% elif tab == 'api':
    <div class="stats-banner" style="justify-content: flex-start; margin-bottom: 32px;">
        <div class="stat-item" style="text-align: left;">
            <div class="stat-lbl">Endpoint Racine</div>
            <div class="stat-val font-mono" style="font-size: 1.1rem; color: var(--primary);">{{BASE_PATH}}/api</div>
        </div>
    </div>
    
    % for doc in api_docs:
        % color = "var(--secondary)" if doc["method"] == "GET" else "var(--tertiary)"
        <div class="card luminescent-border" style="border-left: 4px solid {{color}};">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="background: {{color}}; color: var(--bg); padding: 4px 10px; border-radius: var(--radius); font-weight: 800; font-size: 0.75rem; font-family: var(--font-mono);">{{doc['method']}}</span>
                    <h3 style="margin: 0; font-family: var(--font-mono); font-size: 1.1rem;">{{doc['endpoint']}}</h3>
                </div>
            </div>
            <p style="margin-bottom: 24px; line-height: 1.6;">{{!doc['desc'].replace('\n', '<br>')}}</p>

            % if doc['headers']:
            <div class="nav-label" style="padding-left: 0; margin-bottom: 8px;">Headers attendus</div>
            <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); color: var(--on-surface-variant); font-size: 0.85rem;">{{doc['headers']}}</pre>
            % end

            % if doc['usage']:
            <div class="nav-label" style="padding-left: 0; margin-bottom: 8px; margin-top: 20px;">Exemple d'usage</div>
            <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); color: var(--primary); font-size: 0.85rem;">{{doc['usage']}}</pre>
            % end

            % if doc['payload']:
            <div class="nav-label" style="padding-left: 0; margin-bottom: 8px; margin-top: 20px;">Payload JSON</div>
            <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); color: var(--secondary); font-size: 0.85rem;">{{doc['payload']}}</pre>
            % end

            % if doc['reponse']:
            <div class="nav-label" style="padding-left: 0; margin-bottom: 8px; margin-top: 20px;">Réponse attendue</div>
            <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); color: var(--on-surface); font-size: 0.85rem;">{{doc['reponse']}}</pre>
            % end
        </div>
    % end

% elif tab == 'env':
    <div class="card luminescent-border">
        <h3 style="margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <span class="material-symbols-outlined text-primary">person</span>
            Identité OAuth2 (En-têtes Nginx)
        </h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px;">
            <div class="system-badge">
                <span class="material-symbols-outlined text-primary">alternate_email</span>
                <div>
                    <div class="system-title">X_EMAIL</div>
                    <div class="system-version font-mono" style="text-transform: none;">{{auth_email}}</div>
                </div>
            </div>
            <div class="system-badge">
                <span class="material-symbols-outlined text-secondary">badge</span>
                <div>
                    <div class="system-title">X_USER</div>
                    <div class="system-version font-mono" style="text-transform: none;">{{auth_user}}</div>
                </div>
            </div>
            <div class="system-badge">
                <span class="material-symbols-outlined text-tertiary">devices</span>
                <div>
                    <div class="system-title">TYPE CLIENT</div>
                    <div class="system-version font-mono" style="text-transform: none;">{{client['client_type']}} ({{client['screen_size']}})</div>
                </div>
            </div>
        </div>
    </div>

    <div class="nav-label" style="padding-left: 0; margin: 32px 0 12px 0;">Variables d'Environnement Processus</div>
    <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr><th>Clé</th><th>Valeur</th></tr>
            </thead>
            <tbody>
                % for key, value in env_vars:
                <tr>
                    <td class="font-mono text-primary" style="font-weight: 700; font-size: 0.85rem;">{{key}}</td>
                    <td class="font-mono text-muted" style="word-break: break-all; font-size: 0.8rem;">{{value}}</td>
                </tr>
                % end
            </tbody>
        </table>
    </div>

% elif tab == 'deploy':
    <div class="card luminescent-border" style="border-left: 4px solid var(--tertiary);">
        <h3 style="margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <span class="material-symbols-outlined text-tertiary">rocket_launch</span>
            Déployer vers la production
        </h3>
        <p class="hint">
            Exécute le vrai flux de déploiement décrit dans <code>OPERATIONS.md</code> :
            commit local (<code>/opt/reports-dev</code>) &rarr;
            <strong>copie vers <code>/var/www/reports</code> (la production)</strong> &rarr;
            rechargement du worker uwsgi de prod &rarr;
            archivage de l'état réel vers <code>/opt/docs-infra</code> &rarr;
            commit + <code>git push</code> vers GitHub.
        </p>
        <p class="hint" style="color: var(--error); font-weight: 600;">
            ⚠️ Cette action écrit directement dans <code>/var/www/reports</code>, la vraie production utilisée par les utilisateurs, et recharge son worker uwsgi. Vérifiez l'aperçu ci-dessous avant de continuer.
        </p>

        <div class="nav-label" style="padding-left: 0; margin-top: 24px;">Modifications en attente dans le bac à sable (historique local)</div>
        % if git_status_error:
        <div class="card" style="border-color: var(--error); color: var(--error);">{{git_status_error}}</div>
        % elif git_status_lignes:
        <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); font-size: 0.85rem; overflow-x: auto;">
% for ligne in git_status_lignes:
{{ligne}}
% end
</pre>
        % else:
        <p class="text-muted">Aucune modification en attente : le bac à sable est identique au dernier commit local.</p>
        % end

        <div class="nav-label" style="padding-left: 0; margin-top: 24px;">Aperçu de ce qui sera écrit dans /var/www/reports (production)</div>
        % if prod_diff_error:
        <div class="card" style="border-color: var(--error); color: var(--error);">{{prod_diff_error}}</div>
        % elif prod_diff_lignes:
        <pre style="background: var(--surface-lowest); padding: 16px; border-radius: var(--radius); border: 1px solid var(--outline-variant); font-size: 0.85rem; overflow-x: auto;">
% for ligne in prod_diff_lignes:
{{ligne}}
% end
</pre>
        % else:
        <p class="text-muted">Aucune différence : la production est déjà identique au bac à sable.</p>
        % end

        <div class="nav-label" style="padding-left: 0; margin-top: 24px;">Config uWSGI (reports.ini vs reports-dev.ini)</div>
        <p class="hint" style="font-size: 0.85rem; margin-bottom: 10px;">Le déploiement ne modifie jamais <code>/etc/uwsgi/apps-enabled/reports.ini</code>. Cette vérification existe suite à l'incident du 12/09/2026 (pythonpath <code>src/</code> manquant en prod &rarr; 500 en boucle).</p>
        % if uwsgi_cfg.get('erreur'):
        <div class="card" style="border-color: var(--error); color: var(--error);">{{uwsgi_cfg['erreur']}}</div>
        % elif uwsgi_cfg.get('manquant_en_prod') or uwsgi_cfg.get('en_trop_en_prod'):
        <div class="card" style="border-color: #d9a441; background: rgba(217, 164, 65, 0.1); color: #d9a441;">
            <span class="material-symbols-outlined icon-inline">warning</span>
            La config diverge au-delà des différences de chemins attendues.
            % if uwsgi_cfg.get('manquant_en_prod'):
            <div style="margin-top: 10px;"><strong>Présent en dev, absent en prod :</strong>
            <pre style="background: var(--surface-lowest); padding: 12px; border-radius: var(--radius); font-size: 0.8rem; overflow-x: auto; color: var(--on-surface);">
% for ligne in uwsgi_cfg['manquant_en_prod']:
{{ligne}}
% end
</pre></div>
            % end
            % if uwsgi_cfg.get('en_trop_en_prod'):
            <div style="margin-top: 10px;"><strong>Présent en prod, absent en dev :</strong>
            <pre style="background: var(--surface-lowest); padding: 12px; border-radius: var(--radius); font-size: 0.8rem; overflow-x: auto; color: var(--on-surface);">
% for ligne in uwsgi_cfg['en_trop_en_prod']:
{{ligne}}
% end
</pre></div>
            % end
        </div>
        % else:
        <p class="text-muted">Configurations cohérentes (aucune différence structurelle au-delà des chemins/socket attendus).</p>
        % end

        % if BASE_PATH != '/reports':
        <div class="form-group" style="margin-top: 24px;">
            <label>Message de commit</label>
            <input type="text" id="deploy-message" class="input-dark" placeholder="Ex: Correction de l'attribution des chantiers aux utilisateurs">
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 12px;">
            <button onclick="lancerDeploiement()" class="btn-primary" style="background: var(--error); border-color: var(--error);">
                <span class="material-symbols-outlined icon-sm">rocket_launch</span> Déployer vers la production
            </button>
        </div>

        <div id="deploy-result" style="margin-top: 24px;"></div>
        % end
    </div>

    <script>
    async function lancerDeploiement() {
        const messageInput = document.getElementById('deploy-message');
        const message = messageInput.value.trim();
        const resultDiv = document.getElementById('deploy-result');

        if (!message) {
            alert("Merci de saisir un message de commit.");
            return;
        }

        const confirmation = prompt("Cette action va ECRIRE DIRECTEMENT dans /var/www/reports (la vraie production), recharger son worker uwsgi, puis archiver et pousser vers GitHub.\n\nTapez DEPLOYER pour confirmer :");
        if (confirmation !== "DEPLOYER") {
            return;
        }

        resultDiv.innerHTML = '<div class="hint">Déploiement en cours...</div>';

        try {
            const res = await fetch('{{BASE_PATH}}/dev/deploy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            const data = await res.json();

            let html = '';
            if (data.steps) {
                html += '<div class="table-scroll"><table class="data-table"><thead><tr><th>Étape</th><th>Statut</th><th>Détail</th></tr></thead><tbody>';
                data.steps.forEach(step => {
                    const color = step.ok ? 'var(--secondary)' : 'var(--error)';
                    const icon = step.ok ? 'check_circle' : 'error';
                    html += `<tr><td>${step.label}</td><td style="color: ${color};"><span class="material-symbols-outlined icon-sm">${icon}</span></td><td><pre style="white-space: pre-wrap; font-size: 0.8rem; margin: 0;">${step.output || ''}</pre></td></tr>`;
                });
                html += '</tbody></table></div>';
            }

            if (data.warnings && data.warnings.length > 0) {
                data.warnings.forEach(w => {
                    html += `<div class="card" style="border-color: #d9a441; background: rgba(217, 164, 65, 0.1); color: #d9a441; margin-top: 16px;"><span class="material-symbols-outlined icon-inline">warning</span> ${w}</div>`;
                });
            }

            if (data.error) {
                html += `<div class="card" style="border-color: var(--error); background: rgba(147, 0, 10, 0.1); color: var(--error); margin-top: 16px;"><span class="material-symbols-outlined icon-inline">error</span> ${data.error}</div>`;
            } else if (data.status === 'ok') {
                html += `<div class="card" style="border-color: var(--secondary); background: rgba(74, 225, 118, 0.1); color: var(--secondary); margin-top: 16px;"><span class="material-symbols-outlined icon-inline">check_circle</span> ${data.message}</div>`;
            }

            resultDiv.innerHTML = html;
        } catch (e) {
            resultDiv.innerHTML = `<div class="card" style="border-color: var(--error); color: var(--error);">Erreur réseau : ${e.message}</div>`;
        }
    }
    </script>
% end
