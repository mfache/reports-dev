<div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 6px; border: 1px solid var(--border-color);">
    <div style="display: flex; align-items: center; gap: 8px;">
        <label style="font-size: 0.85em; color: var(--text-muted);">Statut :</label>
        <select id="filter-status" onchange="filterNodesTable()" style="background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 4px; outline: none;">
            <option value="">Tous</option>
            <option value="en ligne">En ligne</option>
            <option value="absent récent">Absent récent</option>
            <option value="hors ligne">Hors ligne</option>
            <option value="jamais">Jamais</option>
        </select>
    </div>
    <div style="display: flex; align-items: center; gap: 8px; flex-grow: 1;">
        <label style="font-size: 0.85em; color: var(--text-muted);">Recherche :</label>
        <input type="text" id="filter-search" onkeyup="filterNodesTable()" placeholder="Hostname, Chantier, IP..." style="width: 100%; background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 5px 10px; border-radius: 4px; outline: none;">
    </div>
</div>

<div style="background: var(--card-bg); border-radius: 8px; border: 1px solid var(--border-color); overflow-x: auto;">
    <table id="nodes-table" style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9em;">
        <thead>
            <tr style="background: var(--header-bg); border-bottom: 1px solid var(--border-color);">
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 0, 'num', this)">ID <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 1, 'str', this)">Hostname <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 2, 'str', this)">Tailscale <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 3, 'str', this)">Chantier <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 4, 'str', this)">Présence <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 5, 'str', this)">Dernière synchro <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none;" onclick="window.sortTable('nodes-table', 6, 'str', this)">Dernière IP <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none; text-align: center;" onclick="window.sortTable('nodes-table', 7, 'num', this)">Points config <span class="sort-icon"></span></th>
                <th style="padding: 12px 16px; font-weight: bold; color: var(--accent-cyan); cursor: pointer; user-select: none; text-align: center;" onclick="window.sortTable('nodes-table', 8, 'num', this)">Relevés <span class="sort-icon"></span></th>
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
            %           status_color = "#22c55e"
            %           status_text = "En ligne"
            %       elif diff_mins < 60:
            %           status_color = "#f59e0b"
            %           status_text = "Absent récent"
            %       else:
            %           status_color = "#ef4444"
            %           status_text = "Hors ligne"
            %       end
            %       sync_str = format_human_date(sync)
            %   else:
            %       status_color = "#64748b"
            %       status_text = "Jamais"
            %       sync_str = "-"
            %   end
            <tr data-status="{{status_text.lower()}}" style="border-bottom: 1px solid var(--border-color); transition: background 0.2s;" onmouseover="this.style.background='var(--hover-bg)'" onmouseout="this.style.background='transparent'">
                <td style="padding: 12px 16px;">{{b['id']}}</td>
                <td style="padding: 12px 16px; font-weight: bold; color: var(--text-main);">{{hn}}</td>
                <td style="padding: 12px 16px; color: var(--text-muted);">{{b['tailscale_name'] or '-'}}</td>
                <td style="padding: 12px 16px; color: var(--accent-orange);">{{b['chantier_ref'] or '-'}}</td>
                <td style="padding: 12px 16px;">
                    <span style="display: inline-flex; align-items: center; gap: 6px;">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background-color: {{status_color}}; display: inline-block;"></span>
                        <span style="color: {{status_color}}; font-size: 0.9em; font-weight: bold;">{{status_text}}</span>
                    </span>
                </td>
                <td style="padding: 12px 16px; color: var(--text-muted);">{{sync_str}}</td>
                <td style="padding: 12px 16px; color: var(--text-muted); font-family: monospace;">{{b['last_ip'] or '-'}}</td>
                <td style="padding: 12px 16px; text-align: center;">{{cc}}</td>
                <td style="padding: 12px 16px; text-align: center;">{{tc}}</td>
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
