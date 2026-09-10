% # Page Développeur "Poupée Moyenne"
<style>
    .mermaid { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow-x: auto; margin-bottom: 30px; display: flex; justify-content: center; }
    table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 40px; font-size: 0.9em; }
    th, td { border: 1px solid #e1e1e1; padding: 10px; text-align: left; }
    th { background-color: #f2f2f2; font-weight: bold; color: #444; }
    tr:nth-child(even) { background-color: #fcfcfc; }
    code { background: #eee; padding: 2px 5px; border-radius: 4px; color: #d63384; font-weight: bold; }

    .sql-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 30px; border-left: 4px solid #0056b3; }
    textarea { width: 100%; height: 100px; padding: 10px; font-family: monospace; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: #0056b3; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
    button:hover { background: #004494; }
    .error-msg { color: #c62828; font-weight: bold; margin-top: 10px; background: #ffebee; padding: 10px; border-radius: 4px; display: inline-block; }
    .success-msg { color: #2e7d32; font-weight: bold; margin-top: 10px; background: #e8f5e9; padding: 10px; border-radius: 4px; display: inline-block; }
    
    .nav-tabs { background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 30px; display: flex; gap: 20px; border-left: 4px solid #0056b3; }
    .nav-tabs a { text-decoration: none; font-weight: bold; padding-bottom: 5px; transition: color 0.2s; }
    .tab-active { color: #0056b3; border-bottom: 2px solid #0056b3; }
    .tab-inactive { color: #666; border-bottom: 2px solid transparent; }
    .tab-inactive:hover { color: #0056b3; }
</style>

<!-- Chargement de Mermaid JS -->
<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>

<div class="container" style="color: #333;">
    <h1 style="color: #0056b3; margin-top: 0;">🛠️ Espace Développeur</h1>
    
    <div class="nav-tabs">
        <a href="?tab=sql" class="{{'tab-active' if tab == 'sql' else 'tab-inactive'}}">Base de données & SQL</a>
        <a href="?tab=api" class="{{'tab-active' if tab == 'api' else 'tab-inactive'}}">Documentation API</a>
        <a href="?tab=env" class="{{'tab-active' if tab == 'env' else 'tab-inactive'}}">Environnement</a>
    </div>

    % if tab == 'sql':
        <h2>🗄️ Structure de la base MariaDB</h2>

        <div class="sql-container">
            <h2 style="margin-top: 0;">Console SQL</h2>
            <textarea id="sql-query" placeholder="SELECT * FROM chantiers LIMIT 5;"></textarea>
            <button onclick="executeSQL()">Exécuter la requête</button>
            <div id="sql-result" style="margin-top: 15px; overflow-x: auto;"></div>
        </div>

        <script>
        async function executeSQL() {
            const query = document.getElementById('sql-query').value.trim();
            const resultDiv = document.getElementById('sql-result');
            if (!query) return;

            resultDiv.innerHTML = '<span style="color: #666;">Exécution en cours...</span>';

            try {
                const res = await fetch('{{BASE_PATH}}/sql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });

                const data = await res.json();

                if (data.error) {
                    resultDiv.innerHTML = `<div class="error-msg">❌ Erreur : ${data.error}</div>`;
                } else if (data.message) {
                    resultDiv.innerHTML = `<div class="success-msg">✅ ${data.message}</div>`;
                } else if (data.columns && data.rows) {
                    if (data.rows.length === 0) {
                        resultDiv.innerHTML = '<span style="color: #666;">Requête exécutée : 0 résultat.</span>';
                    } else {
                        let tableHtml = '<table><thead><tr>';
                        data.columns.forEach(col => {
                            tableHtml += `<th>${col}</th>`;
                        });
                        tableHtml += '</tr></thead><tbody>';

                        data.rows.forEach(row => {
                            tableHtml += '<tr>';
                            data.columns.forEach(col => {
                                let val = row[col];
                                if (val === null) val = '<span style="color: #aaa; font-style: italic;">NULL</span>';
                                tableHtml += `<td>${val}</td>`;
                            });
                            tableHtml += '</tr>';
                        });

                        tableHtml += '</tbody></table>';
                        resultDiv.innerHTML = `<div class="success-msg" style="margin-bottom: 10px;">✅ ${data.rows.length} ligne(s) récupérée(s).</div>` + tableHtml;
                    }
                }
            } catch (e) {
                resultDiv.innerHTML = `<div class="error-msg">❌ Erreur réseau ou de parsing : ${e.message}</div>`;
            }
        }
        </script>

        <p>Aperçu généré dynamiquement du schéma de base de données.</p>

        <h2>Diagramme Entité-Association (ER)</h2>
        <div class="mermaid">
    {{!mermaid_code}}
        </div>

        <h2>Détail des tables ({{len(tables)}})</h2>
        % for table, cols in tables_info.items():
            <h3>Table : <code>{{table}}</code></h3>
            <table>
                <tr><th>Champ</th><th>Type</th><th>Null</th><th>Clé</th><th>Défaut</th><th>Extra</th></tr>
                % for col in cols:
                <tr>
                    <td>{{col['Field']}}</td>
                    <td style='font-family: monospace;'>{{col['Type']}}</td>
                    <td>{{col['Null']}}</td>
                    <td><strong>{{col['Key']}}</strong></td>
                    <td>{{col['Default']}}</td>
                    <td><span style='color: #888; font-size: 0.9em;'>{{col['Extra']}}</span></td>
                </tr>
                % end
            </table>
        % end

    % elif tab == 'api':
        <h2>📖 Documentation des API Boîtiers</h2>
        <p>Liste des endpoints disponibles (préfixe <code>{{BASE_PATH}}/api</code>) pour la communication avec les boîtiers sur le terrain.</p>
        
        % for doc in api_docs:
            % color = "#22c55e" if doc["method"] == "GET" else "#eab308"
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 4px solid {{color}};">
                <h3 style="margin-top: 0; display: flex; align-items: center; gap: 10px;">
                    <code style="background: {{color}}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em;">{{doc['method']}}</code>
                    <strong>{{doc['endpoint']}}</strong>
                </h3>
                <p style="margin-bottom: 20px;">{{!doc['desc'].replace('\n', '<br>')}}</p>

                % if doc['headers']:
                <div style="margin-bottom: 15px;">
                    <strong>Headers attendus :</strong>
                    <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{{doc['headers']}}</pre>
                </div>
                % end

                % if doc['usage']:
                <div style="margin-bottom: 15px;">
                    <strong>Exemple d'usage :</strong>
                    <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{{doc['usage']}}</pre>
                </div>
                % end

                % if doc['payload']:
                <div style="margin-bottom: 15px;">
                    <strong>Exemple de Payload JSON :</strong>
                    <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{{doc['payload']}}</pre>
                </div>
                % end

                % if doc['reponse']:
                <div>
                    <strong>Exemple de Réponse :</strong>
                    <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{{doc['reponse']}}</pre>
                </div>
                % end
            </div>
        % end

    % elif tab == 'env':
        <h2>👤 Identité OAuth2</h2>
        <div style="background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 30px; border-left: 4px solid #0056b3;">
            <p><strong>Email détecté (X_EMAIL) :</strong> <code>{{auth_email}}</code></p>
            <p><strong>Utilisateur détecté (X_USER) :</strong> <code>{{auth_user}}</code></p>
        </div>

        <h2>🌱 Variables d'environnement</h2>
        <p>Liste des variables d'environnement accessibles par le processus Python (<em>Total : {{len(env_vars)}}</em>).</p>
        <table>
            <thead>
                <tr><th>Variable</th><th>Valeur</th></tr>
            </thead>
            <tbody>
                % for key, value in env_vars:
                <tr>
                    <td><code>{{key}}</code></td>
                    <td style='word-break: break-all;'>{{value}}</td>
                </tr>
                % end
            </tbody>
        </table>
    % end
</div>
