% # Page Développeur "Poupée Moyenne" (Kinetic Infrastructure)
<div class="header-with-actions">
    <div>
        <h2>🛠️ Espace Développeur</h2>
        <p class="hint">Outils de diagnostic, introspection de la base de données et documentation API.</p>
    </div>
</div>

<div class="nav-tabs" style="border-left: none; background: var(--surface-low); margin-bottom: 24px; padding: 5px; border-radius: var(--radius-lg); display: inline-flex; gap: 5px;">
    <a href="?tab=sql" class="{{'tab-active' if tab == 'sql' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">SQL & DB</a>
    <a href="?tab=api" class="{{'tab-active' if tab == 'api' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">Doc API</a>
    <a href="?tab=env" class="{{'tab-active' if tab == 'env' else 'tab-inactive'}}" style="border-bottom: none; border-radius: var(--radius-md); padding: 8px 20px;">Système</a>
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
% end
