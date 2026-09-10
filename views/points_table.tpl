% hostname_safe = "".join([c if c.isalnum() else "-" for c in hostname])
<div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 6px; border: 1px solid var(--border-color);">
    <div style="display: flex; align-items: center; gap: 8px;">
        <label style="font-size: 0.85em; color: var(--text-muted);">Protocole :</label>
        <select id="filter-proto-{{hostname_safe}}" onchange="filterTable('{{hostname_safe}}')" style="background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 4px; outline: none;">
            <option value="">Tous</option>
            % for proto in sorted(list(set(str(p['protocol']) for p in points))):
            <option value="{{proto}}">{{proto}}</option>
            % end
        </select>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <label style="font-size: 0.85em; color: var(--text-muted);">Device :</label>
        <select id="filter-dev-{{hostname_safe}}" onchange="onDeviceFilterChange('{{hostname_safe}}'); filterTable('{{hostname_safe}}')" style="background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 4px; outline: none;">
            <option value="">Tous</option>
            % for dev in sorted(list(set(str(p['device']) for p in points))):
            <option value="{{dev}}">{{dev}}</option>
            % end
        </select>
        <button id="btn-purge-dev-{{hostname_safe}}"
                type="button"
                data-chantier-id="{{chantier['id']}}"
                data-hostname="{{hostname}}"
                data-hostname-safe="{{hostname_safe}}"
                onclick="purgeSelectedDeviceFromFilter(this)"
                style="display: none; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #ef4444; padding: 4px 10px; border-radius: 4px; font-size: 0.85em; font-weight: bold; cursor: pointer; transition: all 0.2s;"
                title="Purger tous les relevés de cet équipement">
            🗑️ Purger cet équipement
        </button>
    </div>
    <div style="display: flex; align-items: center; gap: 8px; flex-grow: 1;">
        <label style="font-size: 0.85em; color: var(--text-muted);">Recherche :</label>
        <input type="text" id="filter-search-{{hostname_safe}}" onkeyup="filterTable('{{hostname_safe}}')" placeholder="Mots-clés (ex: AHU Temp)..." style="width: 100%; background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); padding: 5px 10px; border-radius: 4px; outline: none;">
    </div>
</div>
<table id="table-{{hostname_safe}}" style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em;">
    <thead>
        <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-muted); text-align: left;">
            
            <th style="padding: 8px; cursor: pointer; user-select: none;" onclick="window.sortTable('table-{{hostname_safe}}', 0, 'str', this)">Protocole <span class="sort-icon"></span></th>
            <th style="padding: 8px; cursor: pointer; user-select: none;" onclick="window.sortTable('table-{{hostname_safe}}', 1, 'str', this)">Device / Équipement <span class="sort-icon"></span></th>
            <th style="padding: 8px; cursor: pointer; user-select: none;" onclick="window.sortTable('table-{{hostname_safe}}', 2, 'str', this)">Objet / Registre <span class="sort-icon"></span></th>
            <th style="padding: 8px; cursor: pointer; user-select: none;" onclick="window.sortTable('table-{{hostname_safe}}', 3, 'str', this)">Label / Description <span class="sort-icon"></span></th>
            <th style="padding: 8px; cursor: pointer; user-select: none; text-align: right;" onclick="window.sortTable('table-{{hostname_safe}}', 4, 'num', this)">Valeur <span class="sort-icon"></span></th>
            <th style="padding: 8px; cursor: pointer; user-select: none; text-align: center;" onclick="window.sortTable('table-{{hostname_safe}}', 5, 'num', this)">Relevés <span class="sort-icon"></span></th>
            <th style="width: 25px;"></th>
        </tr>
    </thead>
    <tbody>
        % for p in points:
        <tr data-protocol="{{p['protocol']}}" data-device="{{p['device']}}" data-obj="{{p['obj']}}" data-b="{{hostname}}" style="border-bottom: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: background 0.2s;" onclick="toggleRowSelection(this)" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                        <td style="padding: 8px; color: var(--accent-cyan);">{{p['protocol']}}</td>
            <td style="padding: 8px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span>
                        % if p['protocol'].lower() == 'bacnet' and str(p['device']) in bacnet_aliases:
                            <span title="Device ID: {{p['device']}}" style="cursor: help; color: var(--accent-orange); font-weight: bold; border-bottom: 1px dotted var(--accent-orange);">
                                {{bacnet_aliases[str(p['device'])]}}
                            </span>
                        % else:
                            {{p['device']}}
                        % end
                    </span>
                    <button type="button"
                            title="Purger les relevés de l'équipement {{p['device']}}"
                            data-chantier-id="{{chantier['id']}}"
                            data-hostname="{{hostname}}"
                            data-protocol="{{p['protocol']}}"
                            data-device="{{p['device']}}"
                            onclick="event.stopPropagation(); purgeDeviceFromButton(this);"
                            style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 2px 5px; font-size: 0.85em; opacity: 0.35; transition: opacity 0.2s, color 0.2s; border-radius: 3px;"
                            onmouseover="this.style.opacity='1'; this.style.color='#ef4444';"
                            onmouseout="this.style.opacity='0.35'; this.style.color='var(--text-muted)';">
                        🗑️
                    </button>
                </div>
            </td>
            <td style="padding: 8px; font-family: monospace; color: #94a3b8;">{{p['obj']}}</td>
            <td class="point-label" style="padding: 8px; transition: all 0.2s;">{{p['label'] or '—'}}</td>
            <td style="padding: 8px; text-align: right; font-family: monospace; font-weight: bold; color: var(--text-main);">
                <span class="trend-indicator" data-b="{{hostname}}" data-p="{{p['protocol']}}" data-d="{{p['device']}}" data-o="{{p['obj']}}">
                    % if p['trend_dir'] == 'up':
                        <span style="color: #22c55e; font-size: 0.85em; margin-right: 5px;">▲</span>
                    % elif p['trend_dir'] == 'down':
                        <span style="color: #ef4444; font-size: 0.85em; margin-right: 5px;">▼</span>
                    % elif p['trend_dir'] == 'stable':
                        <span style="color: #94a3b8; font-size: 0.85em; margin-right: 5px;">=</span>
                    % elif p['trend_dir'] == 'diff':
                        <span style="color: var(--accent-orange); font-size: 0.85em; margin-right: 5px;">🔄</span>
                    % end
                </span>
                <span class="trend-val-val"
                      data-b="{{hostname}}"
                      data-p="{{p['protocol']}}"
                      data-d="{{p['device']}}"
                      data-o="{{p['obj']}}"
                      data-raw-val="{{p['last_value'] if p['last_value'] is not None else ''}}"
                      style="transition: color 0.5s ease;">
                    {{p['last_value'] if p['last_value'] is not None else '—'}}
                </span>
            </td>
            <td style="padding: 8px; text-align: center;">
                <span class="trend-count-val"
                      data-b="{{hostname}}"
                      data-p="{{p['protocol']}}"
                      data-d="{{p['device']}}"
                      data-o="{{p['obj']}}"
                      style="{{'color: var(--accent-cyan); font-weight: bold;' if p['trend_count'] > 0 else 'color: var(--text-muted); font-size: 0.9em;'}}">
                    {{p['trend_count']}}
                </span>
            </td>
            <td style="padding: 8px; text-align: center; vertical-align: middle;">
                <span class="update-indicator" 
                      data-b="{{hostname}}"
                      data-p="{{p['protocol']}}"
                      data-d="{{p['device']}}"
                      data-o="{{p['obj']}}"
                      style="opacity: 0; transition: opacity 0.3s ease; color: #22c55e; text-shadow: 0 0 5px #22c55e; font-size: 1.2em;">
                    ●
                </span>
            </td>
        </tr>
        % end
    </tbody>
</table>
