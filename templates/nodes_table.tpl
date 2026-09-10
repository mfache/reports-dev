<div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px; align-items: flex-end;">
    <div class="form-group" style="margin-bottom: 0; flex-grow: 1;">
        <label for="filter-search">Recherche instantanée :</label>
        <div style="position: relative;">
            <span class="material-symbols-outlined" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--outline);">search</span>
            <input type="text" id="filter-search" onkeyup="filterNodesTable()" placeholder="Hostname, Chantier, IP..." class="input-dark" style="padding-left: 35px;">
        </div>
    </div>
    <div class="form-group" style="margin-bottom: 0; min-width: 180px;">
        <label for="filter-status">Statut :</label>
        <select id="filter-status" onchange="filterNodesTable()" class="input-dark">
            <option value="">Tous les statuts</option>
            <option value="en ligne">🟢 En ligne</option>
            <option value="absent récent">🟠 Absent récent</option>
            <option value="hors ligne">🔴 Hors ligne</option>
            <option value="jamais">⚪ Jamais</option>
        </select>
    </div>
</div>

<div class="table-scroll">
    <table id="nodes-table" class="data-table">
        <thead>
            <tr>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 0, 'num', this)">ID <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 1, 'str', this)">Hostname <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 2, 'str', this)">Tailscale <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 3, 'str', this)">Chantier <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 4, 'str', this)">Présence <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 5, 'str', this)">Dernière synchro <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('nodes-table', 6, 'str', this)">Dernière IP <span class="sort-icon"></span></th>
                <th style="text-align: center; cursor: pointer;" onclick="window.sortTable('nodes-table', 7, 'num', this)">Points <span class="sort-icon"></span></th>
                <th style="text-align: center; cursor: pointer;" onclick="window.sortTable('nodes-table', 8, 'num', this)">Relevés <span class="sort-icon"></span></th>
            </tr>
        </thead>
        <tbody>
            % import datetime
            % now = datetime.datetime.now()
            % for b in boitiers:
            %   hn = b['hostname']
            %   tc = trends_count.get(hn, 0)
            %   cc = config_count.get(hn, 0)
            %   sync = b['last_sync_at']
            %   if sync:
            %       diff_mins = (now - sync).total_seconds() / 60.0
            %       if diff_mins < 15:
            %           status_color = "var(--secondary)"
            %           status_text = "En ligne"
            %           pulse_class = "pulse-dot"
            %       elif diff_mins < 60:
            %           status_color = "var(--tertiary)"
            %           status_text = "Absent récent"
            %           pulse_class = ""
            %       else:
            %           status_color = "var(--error)"
            %           status_text = "Hors ligne"
            %           pulse_class = ""
            %       end
            %       sync_str = format_human_date(sync)
            %   else:
            %       status_color = "var(--outline)"
            %       status_text = "Jamais"
            %       sync_str = "-"
            %       pulse_class = ""
            %   end
            <tr data-status="{{status_text.lower()}}">
                <td>{{b['id']}}</td>
                <td class="text-primary" style="font-weight: bold;">{{hn}}</td>
                <td class="text-muted">{{b['tailscale_name'] or '-'}}</td>
                <td class="text-tertiary">{{b['chantier_ref'] or '-'}}</td>
                <td>
                    <span style="display: inline-flex; align-items: center; gap: 8px;">
                        <span class="{{pulse_class}}" style="width: 8px; height: 8px; border-radius: 50%; background-color: {{status_color}};"></span>
                        <span style="color: {{status_color}}; font-weight: 600;">{{status_text}}</span>
                    </span>
                </td>
                <td class="text-muted">{{sync_str}}</td>
                <td class="font-mono" style="font-size: 0.8rem; color: var(--on-surface-variant);">{{b['last_ip'] or '-'}}</td>
                <td style="text-align: center;">{{cc}}</td>
                <td style="text-align: center;" class="text-primary">{{tc}}</td>
            </tr>
            % end
        </tbody>
    </table>
</div>

<script>
function filterNodesTable() {
    window.genericTableFilter(
        'nodes-table',
        'filter-search',
        [
            { inputId: 'filter-status', attr: 'data-status' }
        ]
    );
}
</script>
